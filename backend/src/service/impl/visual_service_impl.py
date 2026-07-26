from __future__ import annotations

import base64
import io
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Optional

import cv2
import numpy as np
from PIL import Image
from service.impl.interval_service_impl import IntervalServiceImpl

from utils.api_logger import get_logger
from utils.vlm_client import VLMClient
from service.visual_service import VisualService

log = get_logger(__name__)

def draw_grid_on_image(image_pil: Image.Image, rows: int = 2, cols: int = 4) -> Image.Image:
    image_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    h, w, _ = image_cv.shape
    block_width = w // cols
    block_height = h // rows
    for i in range(1, cols):
        cv2.line(image_cv, (i * block_width, 0), (i * block_width, h), (0, 0, 255), 2)
    for i in range(1, rows):
        cv2.line(image_cv, (0, i * block_height), (w, i * block_height), (0, 0, 255), 2)
    for row in range(rows):
        for col in range(cols):
            block_num = row * cols + col + 1
            text_pos = (col * block_width + 20, row * block_height + 60)
            cv2.putText(
                image_cv, str(block_num), text_pos,
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 0), 3,
            )
    return Image.fromarray(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))

@dataclass
class VlmResponse:
    text: str = ""

_last_call_time: dict[str, float] = {}

def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "rate limit" in msg or "rate_limited" in msg

def _make_vlm_call(client: VLMClient, prompt: str, image_pil: Image.Image, min_interval: float, log: Callable[[str], None], max_retries: int = 3) -> VlmResponse:
    global _last_call_time
    provider = client.provider
    last = _last_call_time.get(provider, 0.0)
    elapsed = time.time() - last
    if elapsed < min_interval:
        wait = min_interval - elapsed
        log(f"Rate limiter: waiting {wait:.2f} s before next VLM call")
        time.sleep(wait)

    buffered = io.BytesIO()
    image_pil.save(buffered, format="JPEG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    for attempt in range(1, max_retries + 1):
        try:
            log(f"Calling {client.provider} API (attempt {attempt}/{max_retries})")
            response = client.chat(prompt, images=[img_b64])
            _last_call_time[provider] = time.time()
            return VlmResponse(text=response or "")
        except Exception as e:
            if _is_rate_limit(e):
                wait = min(60, 10 * 2 ** (attempt - 1))
                log(f"Rate limited. Waiting {wait}s before retry ({attempt}/{max_retries})")
                time.sleep(wait)
            else:
                log(f"VLM API error: {e}")
                return VlmResponse()
    log("VLM API error: max retries reached")
    return VlmResponse()

RELATION_VOCABULARY: list[tuple[str, str]] = [
    ("enter_or_exit_vehicle", "(PersonID, VehicleID)"),
    ("running", "(PersonID)"),
    ("carrying", "(PersonID, ObjectID)"),
    ("suspicious_near_vehicle", "(PersonID, VehicleID)"),
    ("physical_altercation", "(PersonID1, PersonID2, ...)"),
    ("vehicle_collision", "(VehicleID)"),
    ("gunshot_visible", "(PersonID)"),
    ("explosion_visible", "(VehicleID?, ObjectID?)"),
]

def _format_relation_vocabulary() -> str:
    descriptions = {
        "enter_or_exit_vehicle": "A person is entering or exiting any vehicle: car, motorcycle, truck, or van.",
        "running": "A person is running. To better determine if they are running, look at the position of legs and arms; if they are more extended or farther from the body compared to walking, especially the arms which are only extended when walking.",
        "carrying": "A person is transporting an object of class 'object' (package, suitcase, bag) while walking or moving with it. A person can carry an object AND perform other actions (gesturing, running) simultaneously.",
        "suspicious_near_vehicle": "A person is very close to a vehicle that is not theirs, observing it carefully or touching it suspiciously. Do NOT use for simple passersby.",
        "physical_altercation": "Two or more people are involved in aggressive behavior: fighting, pushing, hitting, punching, aggressive gestures, or throwing objects. Include IDs of all people involved.",
        "vehicle_collision": "A vehicle has visible damage from a collision: broken windshield, dented hood, deployed airbags, smoke from engine compartment, or another object embedded in the vehicle.",
        "gunshot_visible": "A person is holding or firing a gun: visible muzzle flash, gun in hand, recoil motion, or smoke from the barrel.",
        "explosion_visible": "A visible explosion: fireball, large smoke cloud, debris flying through the air, or shattered windows. Report the VehicleID or nearest object ID.",
    }
    lines = []
    for name, sig in RELATION_VOCABULARY:
        desc = descriptions.get(name, "")
        lines.append(f"- {name}{sig}: {desc}")
    return "\n".join(lines)

def _build_object_prompt_first_frame(grid_rows: int, grid_cols: int) -> str:
    return f"""Analyze the image with a {grid_rows}x{grid_cols} grid. Identify ALL people, vehicles, and objects.

Your output MUST be a JSON list. Each object MUST have the keys
"class", "description", and "blocks".

CRITICAL class rules (highest priority):
  1. Transportable objects (suitcases, packages, bags, backpacks, envelopes)
     MUST use class 'object'.
  2. ALL people use class 'person'. Do not miss any person.
  3. Cars, trucks, vans use class 'car'. Other vehicles use 'vehicle'.
     Bicycles use 'bike'.
  4. Other objects (chairs, tables, cups, phones) use their specific name.

"description": purely visual details (colors, clothing, shape). Do NOT
mention position or blocks.

"blocks": list of grid block numbers where the object appears. An object
spanning multiple blocks should list ALL of them.

Example:
[{{"class": "person", "description": "man in blue jacket", "blocks": [2, 6]}},
 {{"class": "object", "description": "black suitcase", "blocks": [6]}},
 {{"class": "car", "description": "white sedan", "blocks": [3, 4, 7, 8]}},
 {{"class": "person", "description": "woman with backpack", "blocks": [7]}}]

Provide ONLY the JSON list."""

def _build_object_prompt_tracking_frame(
    grid_rows: int, grid_cols: int, previous_objects: list[dict]
) -> str:
    ctx_lines = [
        f"- ID: {obj['id']}, Class: {obj.get('class')}, Desc: {obj.get('description')}, Blocks: {obj.get('blocks')}"
        for obj in previous_objects
    ]
    ctx = "\n".join(ctx_lines) if ctx_lines else "(none)"
    return f"""Previous objects from the last frame:
{ctx}

Now analyze this NEW image with a {grid_rows}x{grid_cols} grid.
Identify ALL objects present and TRACK them by assigning IDs.

CRITICAL rules for "class" key:
  1. Transportable objects (suitcases, packages, bags) MUST use 'object'.
  2. People: 'person'. Cars: 'car'. Other vehicles: 'vehicle'. Bikes: 'bike'.
  3. Other objects: their specific name.

Output MUST be a JSON list. Each object MUST have:
  - "class": the object category (see rules above)
  - "description": updated visual description (colors, clothing)
  - "blocks": list of grid blocks where the object is now
  - "id": the numeric ID from the previous frame if same object, or the string "new" if never seen before

ID reassignment rules:
  - Same class + overlapping blocks -> likely same object -> reuse ID
  - Same class + close blocks -> likely same object (moved) -> reuse ID
  - Objects that left the frame should NOT appear in the output
  - DO NOT reuse IDs for different-class objects
  - If unsure, assign "new" rather than reusing an ID incorrectly

Provide ONLY the JSON list."""

def _build_relation_prompt(relation_vocabulary: str, objects_ctx: str) -> str:
    return f"""Objects with their IDs and classes:
{objects_ctx}

Analyze the image and output ALL interactions you see using ONLY the
numeric IDs provided. A single person can do multiple things at once.

You MUST consider EACH of the following relation types and output any
that apply:

MANDATORY RELATIONS (output all that apply):

1. running(PersonID)
   The person's body is in a running posture: legs visibly apart, arms
   extended away from the body, or the person is clearly moving fast.
   WALKING is NOT running. Look at leg and arm positions carefully.

2. enter_or_exit_vehicle(PersonID, VehicleID)
   The person is opening a car door, getting into or out of a car,
   motorcycle, truck, or any vehicle. If a person is very close to
   a vehicle door or seat, report this.

3. carrying(PersonID, ObjectID)
   The person is holding, carrying, or transporting any object of class
   'object' (package, suitcase, bag, backpack). Report for ANY person
   touching or holding a transportable item, even briefly.

4. suspicious_near_vehicle(PersonID, VehicleID)
   The person is standing right next to a vehicle, inspecting it,
   or positioned very close to it in a way that draws attention.

5. physical_altercation(PersonID1, PersonID2)
   Two or more people are involved in aggressive behavior: fighting,
   pushing, hitting, punching, making aggressive gestures, or throwing
   objects at each other. Include IDs of all people involved.

6. vehicle_collision(VehicleID)
   A vehicle has visible collision damage: broken windshield, dented
   hood or doors, deployed airbags, smoke from the hood, or another
   object embedded in the vehicle.

7. gunshot_visible(PersonID)
    A person is holding or firing a gun: visible muzzle flash, gun
    in hand, recoil motion, or smoke from the barrel.

8. explosion_visible(VehicleID?, ObjectID?)
    A visible explosion: fireball, large smoke cloud, debris flying
    through the air, or shattered windows. Report the VehicleID or
    nearest object ID.

--- FORMAT ---
Output a single line with space-separated relations.
Example: running(2) enter_or_exit_vehicle(2, 20)

If NONE of the above relations apply, output: none()

Do NOT output any other text."""

_RELATION_PATTERN = re.compile(r"(\w+)\(([^)]+)\)")

@dataclass
class FrameState:
    objects: dict = field(default_factory=dict)
    next_id: int = 1

def _parse_object_json(raw: str, log: Callable[[str], None]) -> list[dict]:
    text = raw.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(text)
    except Exception as e:
        log(f"Failed to parse object JSON: {e}")
        return []
    if not isinstance(parsed, list):
        log("Object JSON is not a list; ignoring")
        return []
    for obj in parsed:
        if isinstance(obj.get("blocks"), (int, float)):
            obj["blocks"] = [int(obj["blocks"])]
        elif not isinstance(obj.get("blocks"), list):
            obj["blocks"] = []
    return parsed

def _persist_object(
    cursor: sqlite3.Cursor, frame_num: int, db_id: int, obj: dict,
    analysis_id: str, log: Callable[[str], None],
) -> None:
    for block in set(obj.get("blocks") or []):
        cursor.execute(
            "INSERT INTO VisualPerFrame (AnalysisID, Frame, ClassID, Class, Block, Description) VALUES (?, ?, ?, ?, ?, ?)",
            (analysis_id, frame_num, db_id, obj.get("class", "unknown"), block, obj.get("description", "")),
        )

def _persist_relation(
    cursor: sqlite3.Cursor,
    frame_num: int,
    event_id: int,
    name: str,
    class_id: str,
    analysis_id: str,
    log: Callable[[str], None],
) -> None:
    cid = int(class_id)
    existing = cursor.execute(
        "SELECT 1 FROM VisualRelation WHERE AnalysisID = ? AND Frame = ? AND RelationType = ? AND ClassID = ?",
        (analysis_id, frame_num, name, cid)
    ).fetchone()
    if existing:
        return
    cursor.execute(
        "INSERT OR IGNORE INTO VisualRelation "
        "(AnalysisID, Frame, RelationID, RelationType, ClassID) "
        "VALUES (?, ?, ?, ?, ?)",
        (analysis_id, frame_num, event_id, name, cid),
    )

def _analyze_frame(
    *,
    frame_num: int,
    frame_grid: Image.Image,
    frame_orig: Image.Image,
    cursor: sqlite3.Cursor,
    state: FrameState,
    client: VLMClient,
    grid_rows: int,
    grid_cols: int,
    min_interval: float,
    max_retries: int = 3,
    analysis_id: str = "",
    track_objects: bool = True,
    log: Callable[[str], None],
) -> FrameState:
    log(f"--- Frame {frame_num} ({client.provider}) ---")

    if not state.objects:
        obj_prompt = _build_object_prompt_first_frame(grid_rows, grid_cols)
    else:
        previous = [{"id": oid, **o} for oid, o in state.objects.items()]
        obj_prompt = _build_object_prompt_tracking_frame(grid_rows, grid_cols, previous)

    response = _make_vlm_call(client, obj_prompt, frame_grid, min_interval, log, max_retries)

    objects = _parse_object_json(response.text, log)
    new_state = FrameState(objects=dict(state.objects), next_id=state.next_id)

    if not state.objects or not track_objects:
        for obj in objects:
            db_id = new_state.next_id
            new_state.next_id += 1
            _persist_object(cursor, frame_num, db_id, obj, analysis_id, log)
            obj["db_id"] = db_id
            new_state.objects[str(db_id)] = obj
            log(f"  -> New object {db_id} ({obj.get('class')})")
    else:
        seen_in_frame: set[str] = set()
        unmatched_existing = set(state.objects.keys())
        for obj in objects:
            raw_id = str(obj.get("id", "new"))
            if raw_id != "new" and raw_id in seen_in_frame:
                log(f"  -> Skipping duplicate object ID '{raw_id}' in same frame")
                continue
            if raw_id != "new":
                seen_in_frame.add(raw_id)
                unmatched_existing.discard(raw_id)
            if raw_id == "new":
                obj_class = obj.get("class", "")
                obj_blocks = set(obj.get("blocks") or [])
                reidentified_id = None
                for eid in list(unmatched_existing):
                    eobj = state.objects[eid]
                    eobj_blocks = set(eobj.get("blocks") or [])
                    if eobj.get("class") != obj_class:
                        continue
                    if obj_blocks and eobj_blocks and not (obj_blocks & eobj_blocks):
                        continue
                    reidentified_id = eid
                    unmatched_existing.discard(eid)
                    break
                if reidentified_id is None:
                    for eid in list(unmatched_existing):
                        eobj = state.objects[eid]
                        if eobj.get("class") != obj_class:
                            continue
                        reidentified_id = eid
                        unmatched_existing.discard(eid)
                        break
                if reidentified_id is not None:
                    db_id = int(reidentified_id)
                    log(f"  -> Re-identified object {db_id} ({obj_class})")
                else:
                    db_id = new_state.next_id
                    new_state.next_id += 1
                    _persist_object(cursor, frame_num, db_id, obj, analysis_id, log)
                    log(f"  -> New object {db_id} ({obj_class})")
            else:
                try:
                    db_id = int(raw_id)
                except (TypeError, ValueError):
                    log(f"  -> Skipping object with malformed id '{raw_id}'")
                    continue
                log(f"  -> Tracked object {db_id}")
            for block in set(obj.get("blocks") or []):
                cursor.execute(
                    "INSERT OR IGNORE INTO VisualPerFrame (AnalysisID, Frame, ClassID, Class, Block, Description) VALUES (?, ?, ?, ?, ?, ?)",
                    (analysis_id, frame_num, db_id, obj.get("class", "unknown"), block, obj.get("description", "")),
                )
            obj["db_id"] = db_id
            new_state.objects[str(db_id)] = obj

    log("Analyzing relations...")
    objects_ctx_lines = [
        f"- ID: {oid}, Desc: {o.get('description')}, Blocks: {o.get('blocks')}"
        for oid, o in new_state.objects.items()
    ]
    objects_ctx = "\n".join(objects_ctx_lines) if objects_ctx_lines else "(no objects)"
    rel_prompt = _build_relation_prompt(_format_relation_vocabulary(), objects_ctx)

    rel_response = _make_vlm_call(client, rel_prompt, frame_orig, min_interval, log, max_retries)

    if rel_response.text:
        rel_text = rel_response.text.strip()
        log(f"Relations: {rel_text}")
        known_class_ids = set(new_state.objects.keys())
        for event_id, (name, args_str) in enumerate(
            _RELATION_PATTERN.findall(rel_text), start=1
        ):
            arg_ids = [a.strip() for a in args_str.split(",")]
            matched_ids = []
            for class_id in arg_ids:
                if class_id in known_class_ids:
                    matched_ids.append(class_id)
                else:
                    log(f"  -> WARNING: VLM hallucinated id '{class_id}', ignored")
            if not matched_ids:
                continue
            for class_id in set(matched_ids):
                _persist_relation(cursor, frame_num, event_id, name, class_id, analysis_id, log)
                log(
                    f"  -> Saved relation: Frame={frame_num}, "
                    f"EventID={event_id}, Type={name}, ClassID={class_id}"
                )

    return new_state

class VisualServiceImpl(VisualService):
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def run_pipeline(
        self,
        *,
        video_path: str,
        conn: sqlite3.Connection,
        client: VLMClient,
        grid_rows: int,
        grid_cols: int,
        sampling_rate: int,
        min_interval: float = 0.0,
        analysis_id: str = "",
        track_objects: bool = True,
        log: Callable[[str], None] = print,
    ) -> None:
        log(f"Starting video analysis: {video_path}")
        log(f"Provider: {client.provider}, Model: {client.model}, Grid: {grid_rows}x{grid_cols}")
        log(f"Sampling rate: 1 frame every {sampling_rate} video frames")

        cursor = conn.cursor()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log(f"ERROR: cannot open video at {video_path}")
            return

        state = FrameState()
        frame_count = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_count % sampling_rate == 0:
                    log(f"--- FRAME {frame_count} ---")
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil = Image.fromarray(rgb)
                    pil_grid = draw_grid_on_image(pil, grid_rows, grid_cols)
                    state = _analyze_frame(
                        frame_num=frame_count,
                        frame_grid=pil_grid,
                        frame_orig=pil,
                        cursor=cursor,
                        state=state,
                        client=client,
                        grid_rows=grid_rows,
                        grid_cols=grid_cols,
                        min_interval=min_interval,
                        max_retries=self.max_retries,
                        analysis_id=analysis_id,
                        track_objects=track_objects,
                        log=log,
                    )
                frame_count += 1
        except Exception as e:
            log(f"CRITICAL ERROR in VLM pipeline: {e}")
        finally:
            cap.release()
        log(f"VLM analysis complete. {frame_count} video frames processed.")
        # Build intervals atomically (frame-level + interval-level in one commit)
        interval_svc = IntervalServiceImpl()
        for msg in interval_svc.build_visual_and_save(conn, sampling_rate, analysis_id=analysis_id, log_fn=log):
            log(msg)
        conn.commit()
