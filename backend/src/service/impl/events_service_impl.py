from __future__ import annotations

from typing import Callable, Iterator

import pandas as pd

from utils.api_logger import get_logger
from service.impl.iseql_helpers import (
    iseql_before,
    iseql_during,
    iseql_overlap,
    iseql_start_preceding,
)
from service.events_service import EventsService, EventSpec

log = get_logger(__name__)

VISUAL_EVENTS: list[EventSpec] = [
    EventSpec("fight", "Fight: physical altercation detected", None, "A"),
    EventSpec("vehicle_escape", "Vehicle Escape: running BEFORE/OVERLAP enter_or_exit_vehicle", "delta_visual_vehicle_escape", "A"),
    EventSpec("loitering", "Loitering: suspicious_near_vehicle WITH duration >= delta", "delta_visual_loitering", "A"),
    EventSpec("handoff", "Handoff: carry(A) BEFORE/OVERLAP carry(B)", "delta_visual_handoff", "A"),
    EventSpec("vehicle_collision", "Vehicle Collision: damaged vehicle detected", None, "A"),
    EventSpec("gunshot_or_explosion", "Gunshot or explosion: gunshot_visible OR explosion_visible", None, "A"),
]

SOUND_EVENTS: list[EventSpec] = [
    EventSpec("fight", "Fight: shout BEFORE impact WITHIN delta", "delta_sound_fight", "B"),
    EventSpec("gunshot_or_explosion", "Gunshot or explosion: gunshot_or_explosion detected", None, "B"),
    EventSpec("vehicle_escape", "Vehicle Escape: engine BEFORE/OVERLAP tire_squeal", "delta_sound_vehicle_escape", "B"),
    EventSpec("vehicle_collision", "Vehicle Collision: horn/skid BEFORE/OVERLAP impact/glass_breaking", "delta_sound_vehicle_collision", "B"),
]

MULTIMODAL_EVENTS: list[EventSpec] = [
    EventSpec("fight", "Fight: (shout BEFORE impact) UNION physical_altercation", None, "C"),
    EventSpec("gunshot_or_explosion", "Gunshot or explosion: gunshot_or_explosion UNION (gunshot_visible OR explosion_visible)", None, "C"),
    EventSpec("vehicle_escape", "Vehicle Escape: (engine BEFORE/OVERLAP tire_squeal) UNION (running BEFORE/OVERLAP enter_or_exit_vehicle)", None, "C"),
    EventSpec("loitering", "Loitering: suspicious_near_vehicle WITH duration >= delta [visual only]", "delta_visual_loitering", "C"),
    EventSpec("handoff", "Handoff: carry(A) BEFORE/OVERLAP carry(B) [visual only]", "delta_visual_handoff", "C"),
    EventSpec("vehicle_collision", "Vehicle Collision: (horn/skid BEFORE/OVERLAP impact/glass_breaking) UNION vehicle_collision_visible", None, "C"),
]


def _build_visual_queries(deltas: dict, analysis_id: str = "") -> dict[str, str]:
    delta_visual_vehicle_escape = int(deltas.get("delta_visual_vehicle_escape", 50))
    delta_visual_loitering = int(deltas.get("delta_visual_loitering", 150))
    delta_visual_handoff = int(deltas.get("delta_visual_handoff", 240))

    a = f"AND VIP.AnalysisID = '{analysis_id}'" if analysis_id else ""
    ip_person = "IP.Class = 'person'"
    ip_vehicle = "IP.Class IN ('car', 'vehicle')"

    return {
        "fight": f"""
            SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame,
                   MIN(IP.ClassID) AS PersonID, MAX(IP.ClassID) AS PersonID2
            FROM VisualPerInterval VIP
            JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
            WHERE VIP.RelationType = 'physical_altercation' AND {ip_person} {a}
            GROUP BY VIP.RelationID
            HAVING COUNT(DISTINCT IP.ClassID) >= 2
        """,

        "vehicle_escape": f"""
            WITH
            EnterExitEvents AS (
                SELECT VIP.RelationID,
                       IP_P.ClassID AS PersonID, IP_V.ClassID AS VehicleID,
                       VIP.StartFrame, VIP.EndFrame
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP_P ON VIP.RelationID = IP_P.RelationID AND IP_P.Class = 'person'
                JOIN VisualParticipant IP_V ON VIP.RelationID = IP_V.RelationID AND IP_V.Class IN ('car', 'vehicle')
                WHERE VIP.RelationType IN ('enter_or_exit_vehicle', 'enter_vehicle', 'exit_vehicle') {a}
            ),
            RunEvents AS (
                SELECT VIP.RelationID,
                       IP.ClassID AS PersonID,
                       VIP.StartFrame, VIP.EndFrame
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'running' AND {ip_person} {a}
            )
            SELECT EEE.RelationID,
                   MIN(EEE.StartFrame, RE.StartFrame) AS StartFrame,
                   MAX(EEE.EndFrame, RE.EndFrame) AS EndFrame,
                   EEE.PersonID, EEE.VehicleID
            FROM EnterExitEvents EEE
            JOIN RunEvents RE ON EEE.PersonID = RE.PersonID
            WHERE ({iseql_before('RE', 'EEE', delta_visual_vehicle_escape)})
               OR ({iseql_overlap('RE', 'EEE')});
        """,

        "loitering": f"""
            SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame,
                   IP_P.ClassID AS PersonID, IP_V.ClassID AS VehicleID
            FROM VisualPerInterval VIP
            JOIN VisualParticipant IP_P ON VIP.RelationID = IP_P.RelationID AND IP_P.Class = 'person'
            JOIN VisualParticipant IP_V ON VIP.RelationID = IP_V.RelationID AND IP_V.Class IN ('car', 'vehicle')
            WHERE VIP.RelationType = 'suspicious_near_vehicle'
              AND IP_P.ClassID != IP_V.ClassID
              AND (VIP.EndFrame - VIP.StartFrame) >= {delta_visual_loitering} {a}
        """,

        "handoff": f"""
            WITH
            CarryAll AS (
                SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame, IP.ClassID AS PersonID
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'carrying' AND {ip_person} {a}
            ),
            CarryObject AS (
                SELECT VIP.RelationID, IP.ClassID AS ObjectID
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'carrying' AND IP.Class = 'object' {a}
            )
            SELECT CA.RelationID,
                   MIN(CA.StartFrame, CA2.StartFrame) AS StartFrame,
                   MAX(CA.EndFrame, CA2.EndFrame) AS EndFrame,
                   CA.PersonID AS GiverID, CA2.PersonID AS ReceiverID,
                   COALESCE(CO.ObjectID, CO2.ObjectID) AS ObjectID
            FROM CarryAll CA
            JOIN CarryAll CA2 ON CA.PersonID != CA2.PersonID AND CA.RelationID != CA2.RelationID
            INNER JOIN CarryObject CO ON CA.RelationID = CO.RelationID
            INNER JOIN CarryObject CO2 ON CA2.RelationID = CO2.RelationID
              AND CO.ObjectID = CO2.ObjectID
            WHERE ({iseql_before('CA', 'CA2', delta_visual_handoff)})
               OR ({iseql_before('CA2', 'CA', delta_visual_handoff)})
               OR ({iseql_overlap('CA', 'CA2')})
        """,

        "vehicle_collision": f"""
            SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame,
                   IP.ClassID AS VehicleID
            FROM VisualPerInterval VIP
            JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
            WHERE VIP.RelationType = 'vehicle_collision'
              AND {ip_vehicle} {a}
        """,

        "gunshot_or_explosion": f"""
            SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame, IP.ClassID AS ClassID
            FROM VisualPerInterval VIP
            JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
            WHERE VIP.RelationType IN ('gunshot_visible', 'explosion_visible')
              {a}
        """,
    }


def _build_sound_queries(deltas: dict, analysis_id: str = "") -> dict[str, str]:
    a = f"AND AnalysisID = '{analysis_id}'" if analysis_id else ""
    delta_sound_fight = int(deltas.get("delta_sound_fight", 120))
    delta_sound_vehicle_escape = int(deltas.get("delta_sound_vehicle_escape", 150))
    delta_sound_vehicle_collision = int(deltas.get("delta_sound_vehicle_collision", 60))
    confidence_threshold = 0.0

    return {
        "fight": f"""
            WITH ShoutSounds AS (
                SELECT SoundIntervalID, StartFrame, EndFrame
                FROM SoundPerInterval SI
                WHERE SoundClass = 'shout' AND Confidence >= {confidence_threshold} {a}
            ),
            ImpactSounds AS (
                SELECT SoundIntervalID, StartFrame, EndFrame
                FROM SoundPerInterval SI
                WHERE SoundClass IN ('impact', 'fight')
                  AND Confidence >= {confidence_threshold} {a}
            )
            SELECT SS.SoundIntervalID,
                   MIN(SS.StartFrame, IMS.StartFrame) AS StartFrame,
                   MAX(SS.EndFrame, IMS.EndFrame) AS EndFrame
            FROM ShoutSounds SS
            JOIN ImpactSounds IMS ON {iseql_before('SS', 'IMS', delta_sound_fight)};
        """,

        "gunshot_or_explosion": f"""
            SELECT SoundIntervalID, StartFrame, EndFrame
            FROM SoundPerInterval SI
            WHERE SoundClass = 'gunshot_or_explosion' AND Confidence >= {confidence_threshold} {a}
            ORDER BY StartFrame;
        """,

        "vehicle_escape": f"""
            WITH EngineSounds AS (
                SELECT SoundIntervalID, StartFrame, EndFrame
                FROM SoundPerInterval SI
                WHERE SoundClass IN ('engine', 'vehicle')
                  AND Confidence >= {confidence_threshold} {a}
            ),
            TireSounds AS (
                SELECT SoundIntervalID, StartFrame, EndFrame
                FROM SoundPerInterval SI
                WHERE SoundClass IN ('tire_squeal')
                  AND Confidence >= {confidence_threshold} {a}
            )
            SELECT ES.SoundIntervalID,
                   MIN(ES.StartFrame, TS.StartFrame) AS StartFrame,
                   MAX(ES.EndFrame, TS.EndFrame) AS EndFrame
            FROM EngineSounds ES
            JOIN TireSounds TS ON ({iseql_before('ES', 'TS', delta_sound_vehicle_escape)})
                               OR ({iseql_overlap('ES', 'TS')});
        """,

        "vehicle_collision": f"""
            WITH PreImpact AS (
                SELECT SoundIntervalID, StartFrame, EndFrame
                FROM SoundPerInterval SI
                WHERE SoundClass IN ('horn', 'skidding')
                  AND Confidence >= {confidence_threshold} {a}
            ),
            GlassSounds AS (
                SELECT SoundIntervalID, StartFrame, EndFrame
                FROM SoundPerInterval SI
                WHERE SoundClass IN ('impact', 'glass_breaking')
                  AND Confidence >= {confidence_threshold} {a}
            )
            SELECT PI.SoundIntervalID,
                   MIN(PI.StartFrame, GS.StartFrame) AS StartFrame,
                   MAX(PI.EndFrame, GS.EndFrame) AS EndFrame
            FROM PreImpact PI
            JOIN GlassSounds GS ON {iseql_before('PI', 'GS', delta_sound_vehicle_collision)} 
                                OR ({iseql_overlap('PI', 'GS')});
        """,
    }


def _build_multimodal_queries(deltas: dict, analysis_id: str = "") -> dict[str, str]:
    a = f"AND VIP.AnalysisID = '{analysis_id}'" if analysis_id else ""
    a_sound = f"AND SI.AnalysisID = '{analysis_id}'" if analysis_id else ""
    delta_visual_vehicle_escape = int(deltas.get("delta_visual_vehicle_escape", 50))
    delta_visual_loitering = int(deltas.get("delta_visual_loitering", 150))
    delta_visual_handoff = int(deltas.get("delta_visual_handoff", 240))
    delta_sound_fight = int(deltas.get("delta_sound_fight", 120))
    delta_sound_vehicle_escape = int(deltas.get("delta_sound_vehicle_escape", 150))
    delta_sound_vehicle_collision = int(deltas.get("delta_sound_vehicle_collision", 60))
    confidence_threshold = 0.0

    ip_person = "IP.Class = 'person'"
    ip_vehicle = "IP.Class IN ('car', 'vehicle')"

    return {
        "fight": f"""
            WITH FightAudio AS (
                WITH ShoutSounds AS (
                    SELECT SoundIntervalID, StartFrame, EndFrame
                    FROM SoundPerInterval SI
                    WHERE SoundClass = 'shout' AND Confidence >= {confidence_threshold} {a_sound}
                ),
                ImpactSounds AS (
                    SELECT SoundIntervalID, StartFrame, EndFrame
                    FROM SoundPerInterval SI
                    WHERE SoundClass IN ('impact', 'fight')
                      AND Confidence >= {confidence_threshold} {a_sound}
                )
                SELECT SS.SoundIntervalID, NULL AS VisualRelationID,
                       SS.StartFrame, SS.EndFrame,
                       NULL AS PersonID, NULL AS PersonID2
                FROM ShoutSounds SS
                JOIN ImpactSounds IMS ON {iseql_before('SS', 'IMS', delta_sound_fight)}
            ),
            Combined AS (
                SELECT SoundIntervalID, VisualRelationID, StartFrame, EndFrame, PersonID, PersonID2 FROM FightAudio
                UNION
                SELECT NULL AS SoundIntervalID, VIP.RelationID AS VisualRelationID,
                       VIP.StartFrame, VIP.EndFrame,
                       MIN(IP.ClassID) AS PersonID, MAX(IP.ClassID) AS PersonID2
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'physical_altercation' AND {ip_person} {a}
                GROUP BY VIP.RelationID
                HAVING COUNT(DISTINCT IP.ClassID) >= 2
            )
            SELECT MAX(VisualRelationID) AS VisualRelationID,
                   MAX(SoundIntervalID) AS SoundIntervalID,
                   MIN(StartFrame) AS StartFrame,
                   MAX(EndFrame) AS EndFrame,
                   MAX(PersonID) AS PersonID,
                   MAX(PersonID2) AS PersonID2
            FROM Combined
            HAVING StartFrame IS NOT NULL;
        """,

        "gunshot_or_explosion": f"""
            SELECT MAX(VisualRelationID) AS VisualRelationID,
                   MAX(SoundIntervalID) AS SoundIntervalID,
                   MIN(StartFrame) AS StartFrame,
                   MAX(EndFrame) AS EndFrame,
                   MAX(ClassID) AS ClassID
            FROM (
                SELECT NULL AS VisualRelationID, SI.SoundIntervalID AS SoundIntervalID,
                       StartFrame, EndFrame,
                       NULL AS ClassID
                FROM SoundPerInterval SI
                WHERE SoundClass = 'gunshot_or_explosion' AND Confidence >= {confidence_threshold} {a_sound}
                UNION
                SELECT VIP.RelationID AS VisualRelationID, NULL AS SoundIntervalID,
                       VIP.StartFrame, VIP.EndFrame,
                       IP.ClassID AS ClassID
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType IN ('gunshot_visible', 'explosion_visible')
                  {a}
            ) HAVING StartFrame IS NOT NULL;
        """,

        "vehicle_escape": f"""
            WITH Combined AS (
                SELECT SoundIntervalID, VisualRelationID, StartFrame, EndFrame, PersonID, VehicleID
                FROM (
                    WITH EngineSounds AS (
                        SELECT SoundIntervalID, StartFrame, EndFrame
                        FROM SoundPerInterval SI
                        WHERE SoundClass IN ('engine', 'vehicle')
                          AND Confidence >= {confidence_threshold} {a_sound}
                    ),
                    TireSounds AS (
                        SELECT SoundIntervalID, StartFrame, EndFrame
                        FROM SoundPerInterval SI
                        WHERE SoundClass IN ('tire_squeal')
                          AND Confidence >= {confidence_threshold} {a_sound}
                    )
                    SELECT ES.SoundIntervalID, NULL AS VisualRelationID,
                           ES.StartFrame AS StartFrame, TS.EndFrame AS EndFrame,
                           NULL AS PersonID, NULL AS VehicleID
                    FROM EngineSounds ES
                    JOIN TireSounds TS ON ({iseql_before('ES', 'TS', delta_sound_vehicle_escape)})
                                       OR ({iseql_overlap('ES', 'TS')})
                ) AudioSeq
                UNION
                SELECT SoundIntervalID, VisualRelationID, StartFrame, EndFrame, PersonID, VehicleID
                FROM (
                    WITH EnterExitEvents AS (
                        SELECT VIP.RelationID,
                               IP_P.ClassID AS PersonID, IP_V.ClassID AS VehicleID,
                               VIP.StartFrame, VIP.EndFrame
                        FROM VisualPerInterval VIP
                        JOIN VisualParticipant IP_P ON VIP.RelationID = IP_P.RelationID AND IP_P.Class = 'person'
                        JOIN VisualParticipant IP_V ON VIP.RelationID = IP_V.RelationID AND IP_V.Class IN ('car', 'vehicle')
                        WHERE VIP.RelationType IN ('enter_or_exit_vehicle', 'enter_vehicle', 'exit_vehicle') {a}
                    ),
                    RunEvents AS (
                        SELECT VIP.RelationID,
                               IP.ClassID AS PersonID,
                               VIP.StartFrame, VIP.EndFrame
                        FROM VisualPerInterval VIP
                        JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                        WHERE VIP.RelationType = 'running' AND {ip_person} {a}
                    )
                    SELECT NULL AS SoundIntervalID, EEE.RelationID AS VisualRelationID,
                           MIN(EEE.StartFrame, RE.StartFrame) AS StartFrame,
                           MAX(EEE.EndFrame, RE.EndFrame) AS EndFrame,
                           EEE.PersonID, EEE.VehicleID
                    FROM EnterExitEvents EEE
                    JOIN RunEvents RE ON EEE.PersonID = RE.PersonID
                    WHERE ({iseql_before('RE', 'EEE', delta_visual_vehicle_escape)})
                       OR ({iseql_overlap('RE', 'EEE')})
                ) VisualSeq
            )
            SELECT MAX(VisualRelationID) AS VisualRelationID,
                   MAX(SoundIntervalID) AS SoundIntervalID,
                   MIN(StartFrame) AS StartFrame,
                   MAX(EndFrame) AS EndFrame,
                   MAX(PersonID) AS PersonID,
                   MAX(VehicleID) AS VehicleID
            FROM Combined HAVING StartFrame IS NOT NULL;
        """,

        "vehicle_collision": f"""
            SELECT MAX(VisualRelationID) AS VisualRelationID,
                   MAX(SoundIntervalID) AS SoundIntervalID,
                   MIN(StartFrame) AS StartFrame,
                   MAX(EndFrame) AS EndFrame,
                   MAX(VehicleID) AS VehicleID
            FROM (
                SELECT NULL AS VisualRelationID, SoundIntervalID, StartFrame, EndFrame, NULL AS VehicleID
                FROM (
                    WITH PreImpact AS (
                        SELECT SoundIntervalID, StartFrame, EndFrame
                        FROM SoundPerInterval SI
                        WHERE SoundClass IN ('horn', 'skidding')
                          AND Confidence >= {confidence_threshold} {a_sound}
                    ),
                    GlassSounds AS (
                        SELECT SoundIntervalID, StartFrame, EndFrame
                        FROM SoundPerInterval SI
                        WHERE SoundClass IN ('impact', 'glass_breaking')
                          AND Confidence >= {confidence_threshold} {a_sound}
                    )
                    SELECT PI.SoundIntervalID,
                           PI.StartFrame AS StartFrame, GS.EndFrame AS EndFrame
                    FROM PreImpact PI
                    JOIN GlassSounds GS ON {iseql_before('PI', 'GS', delta_sound_vehicle_collision)} 
                                        OR ({iseql_overlap('PI', 'GS')})
                ) AudioCollision
                UNION
                SELECT VIP.RelationID AS VisualRelationID, NULL AS SoundIntervalID,
                       VIP.StartFrame, VIP.EndFrame,
                       IP.ClassID AS VehicleID
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'vehicle_collision' AND {ip_vehicle} {a}
            ) HAVING StartFrame IS NOT NULL;
        """,

        "loitering": f"""
            SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame,
                   IP_P.ClassID AS PersonID, IP_V.ClassID AS VehicleID
            FROM VisualPerInterval VIP
            JOIN VisualParticipant IP_P ON VIP.RelationID = IP_P.RelationID AND IP_P.Class = 'person'
            JOIN VisualParticipant IP_V ON VIP.RelationID = IP_V.RelationID AND IP_V.Class IN ('car', 'vehicle')
            WHERE VIP.RelationType = 'suspicious_near_vehicle'
              AND IP_P.ClassID != IP_V.ClassID
              AND (VIP.EndFrame - VIP.StartFrame) >= {delta_visual_loitering} {a}
        """,

        "handoff": f"""
            WITH
            CarryAll AS (
                SELECT VIP.RelationID, VIP.StartFrame, VIP.EndFrame, IP.ClassID AS PersonID
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'carrying' AND {ip_person} {a}
            ),
            CarryObject AS (
                SELECT VIP.RelationID, IP.ClassID AS ObjectID
                FROM VisualPerInterval VIP
                JOIN VisualParticipant IP ON VIP.RelationID = IP.RelationID
                WHERE VIP.RelationType = 'carrying' AND IP.Class = 'object' {a}
            )
            SELECT CA.RelationID,
                   MIN(CA.StartFrame, CA2.StartFrame) AS StartFrame,
                   MAX(CA.EndFrame, CA2.EndFrame) AS EndFrame,
                   CA.PersonID AS GiverID, CA2.PersonID AS ReceiverID,
                   COALESCE(CO.ObjectID, CO2.ObjectID) AS ObjectID
            FROM CarryAll CA
            JOIN CarryAll CA2 ON CA.PersonID != CA2.PersonID AND CA.RelationID != CA2.RelationID
            INNER JOIN CarryObject CO ON CA.RelationID = CO.RelationID
            INNER JOIN CarryObject CO2 ON CA2.RelationID = CO2.RelationID
              AND CO.ObjectID = CO2.ObjectID
            WHERE ({iseql_before('CA', 'CA2', delta_visual_handoff)})
               OR ({iseql_before('CA2', 'CA', delta_visual_handoff)})
               OR ({iseql_overlap('CA', 'CA2')});
        """,

    }


def queries_for_condition(condition: str, deltas: dict, analysis_id: str = "") -> dict[str, str]:
    if condition == "A":
        return _build_visual_queries(deltas, analysis_id)
    if condition == "B":
        return _build_sound_queries(deltas, analysis_id)
    if condition == "C":
        return _build_multimodal_queries(deltas, analysis_id)
    raise ValueError(f"unknown condition '{condition}'; expected A | B | C")


def events_for_condition(condition: str) -> list[EventSpec]:
    if condition == "A":
        return list(VISUAL_EVENTS)
    if condition == "B":
        return list(SOUND_EVENTS)
    if condition == "C":
        return list(MULTIMODAL_EVENTS)
    raise ValueError(f"unknown condition '{condition}'; expected A | B | C")


def run_sql_detection(
    conn,
    event_type: str,
    deltas: dict,
    analysis_id: str = "",
    condition: str = "A",
    log: Callable[[str], None] = log.info,
) -> Iterator[str]:
    queries = queries_for_condition(condition, deltas, analysis_id)
    if event_type not in queries:
        yield f"ERROR: unknown event type '{event_type}' for condition {condition}"
        return
    sql = queries[event_type]
    log(f"Running SQL detection for '{event_type}' (condition {condition}) with deltas {deltas}")
    try:
        df = pd.read_sql_query(sql, conn)
        log(f"--- {len(df)} results ---")
        if df.empty:
            yield "No events of this type were detected."
        else:
            yield f"__RESULT__:{df.to_json(orient='records')}"
    except Exception as e:
        yield f"ERROR executing query: {e}"


class EventsServiceImpl(EventsService):
    def queries_for_condition(self, condition: str, deltas: dict) -> dict[str, str]:
        return queries_for_condition(condition, deltas)

    def events_for_condition(self, condition: str) -> list[EventSpec]:
        return events_for_condition(condition)

    def run_sql_detection(
        self,
        conn,
        event_type: str,
        deltas: dict,
        analysis_id: str = "",
        condition: str = "A",
        log: Callable[[str], None] = None,
    ) -> Iterator[str]:
        return run_sql_detection(conn, event_type, deltas, analysis_id, condition, log or log.info)
