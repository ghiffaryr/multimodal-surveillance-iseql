# Evaluation Scenes: Multimodal ISEQL Temporal Event Detection

30 scenes across 6 event types, each with 5 variations for consistency measurement.
Multimodal (C) evaluated on all scenes; visual-only (A) and sound-only (B) evaluated
on modality-capable scenes only.

## Setup

- **Model**: Dreamina Seedance, single generation per scene, 10 seconds each
- **Camera**: Fixed, surveillance angle (slightly elevated), no zoom, no pan
- **Resolution**: 1280×720, 24 fps
- **Each scene**: generated once with ALL detail in the prompt, no post-production edits
- **Audio pipeline**: PANNs CNN14 or Qwen2-Audio-7B-Instruct → SoundPerFrame → SoundPerInterval
- **Visual pipeline**: VLM (Pixtral 12B, Ministral 3-14B, Gemini 2.5 Flash, Gemini 3.6 Flash) → VisualRelation → VisualPerInterval
- **High-level detection**: ISEQL temporal queries over VisualPerInterval and SoundPerInterval

## Evaluation Methodology

### Modality-Capable Scoping

Each condition is evaluated only on scenes where that modality can physically perceive the event:

| Condition | Eligible scenes | Exclusions |
|-----------|----------------|------------|
| A (visual) | Event visible in-frame | Off-camera / occluded events excluded |
| B (sound) | Event has audio correlate | Handoff, loitering (no sound) excluded |
| C (multimodal) | All scenes | (none) |

### Per-Event Binary Metrics

For each event type, every scene is labeled as positive (contains this event) or negative (does not contain this event). Each condition's output is compared to ground truth:

| | Pipeline says YES | Pipeline says NO |
|--|------------------|-----------------|
| **GT says YES** | TP | FN |
| **GT says NO** | FP | TN |

**Precision = TP / (TP + FP) | Recall = TP / (TP + FN) | F1 = 2PR / (P+R)**

### Consistency Interpretation

With 5 positive scenes per event (where modality-capable), the expected recall is:
- **5/5 = 1.0**: Model detects the event consistently across different visual contexts
- **4/5 = 0.80**: Model misses the event under certain conditions
- **3/5 or less**: Model fails to generalize

---


## Scene 4: Visible Fistfight Near Wall

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot near a wall. Two people
stand facing each other, arguing, arms waving, pointing fingers. Voices raised,
shouting audible.

2-4.5 seconds: The argument escalates. One person shoves the other. The second
person responds by throwing a punch. A physical fight breaks out with both
people throwing punches and pushing each other. Shouting and impact sounds
audible throughout.

4.5-6 seconds: The fight continues with grappling. One person is pushed against
the wall with a loud impact sound.

6-8 seconds: A third person runs into frame and pulls them apart. The fighters
separate, breathing heavily.

8-10 seconds: The two fighters back away from each other. One exits frame left,
the other walks away right. Third person follows. Frame becomes empty.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `fight` = physical_altercation on VisualPerInterval.
- B: `fight` = shout BEFORE impact WITHIN delta_sound_fight on SoundPerInterval.
- C: `fight` = (shout BEFORE impact) UNION physical_altercation.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Physical altercation visible in-frame |
| B    | TP       | Shout BEFORE impact detected as fight sequence |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | shout                     |    0.000 |    1.500 |     0 | 36    | Shouting during argument |
| audio    | impact                    |    1.500 |    1.667 |    36 | 40    | Punches and body impacts during fight |
| visual   | physical_altercation      |    1.583 |    5.625 |    38 | 135   | Two people fighting in-frame |

---


## Scene 5: Visible Fistfight

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot near a wall. Two people
stand facing each other, arguing, arms waving, pointing fingers. Voices raised,
shouting audible.

2-4.5 seconds: The argument escalates. One person shoves the other. The second
person responds by throwing a punch. A physical fight breaks out with both
people throwing punches and pushing each other. Shouting and impact sounds
audible throughout.

4.5-6 seconds: The fight continues with grappling. One person is pushed against
the wall with a loud impact sound.

6-8 seconds: A third person runs into frame and pulls them apart. The fighters
separate, breathing heavily.

8-10 seconds: The two fighters back away from each other. One exits frame left,
the other walks away right. Third person follows. Frame becomes empty.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `fight` = physical_altercation detected on VisualPerInterval → TP.
- B: `fight` = shout BEFORE impact on SoundPerInterval → TP.
- C: `fight` = (shout BEFORE impact) UNION physical_altercation → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Physical altercation visible in-frame |
| B    | TP       | Shout BEFORE impact detected as fight sequence |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | shout                     |    0.000 |    1.833 |     0 | 44    | Shouting and arguing |
| audio    | impact                    |    1.833 |    5.125 |    44 | 123   | Punches and body impacts |
| visual   | physical_altercation      |    2.000 |    6.625 |    48 | 159   | Two people fighting |

---


## Scene 6: Argument With Thrown Object

**Dreamina prompt (10 seconds, exact timing):**

0-2.5 seconds: Fixed security camera view of a parking lot near a dumpster
area. Two people are arguing loudly, standing a few meters apart. Shouting
heard clearly.

2.5-4 seconds: One person picks up an object (a plastic bottle or similar) from
the ground and hurls it toward the other person. The object hits the ground
near them with a loud impact sound. A shout is heard at the moment of throwing.

4-7 seconds: The person who threw the object storms away, continuing to shout
over their shoulder. The other person stands still, then bends down to pick up
the fallen object.

7-10 seconds: Both people exit in opposite directions. The area becomes empty.
Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `fight` = physical_altercation detected on VisualPerInterval → TP.
- B: `fight` = shout BEFORE impact on SoundPerInterval → TP.
- C: `fight` = (shout BEFORE impact) UNION physical_altercation → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Physical altercation (throwing) visible |
| B    | TP       | Shout BEFORE impact detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | shout                     |    0.000 |    2.167 |     0 | 52    | Shouting during argument |
| audio    | impact                    |    2.500 |    3.000 |    60 | 72    | Object hitting ground |
| visual   | physical_altercation      |    2.542 |    2.917 |    61 | 70    | Person throws object aggressively |

---


## Scene 7: Gunshot + Explosion (Gas Leak)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot near a building with a
gas line visible on the exterior wall. A person stands near a car, arguing with
another person a few meters away. Shouting heard.

2-3 seconds: The first person pulls out a gun and fires a shot. The muzzle flash
is clearly visible. The gunshot sound is sharp and distinct. The person is
holding the gun in plain view.

3-5 seconds: The bullet hits the gas line on the building wall. Sparks fly,
then a large explosion erupts: a fireball, smoke, and debris visible. The
explosion sound is a deep boom. Both people duck and run.

5-8 seconds: The fire spreads. People flee in all directions. Smoke billows.
The building wall is damaged with visible debris on the ground.

8-10 seconds: Fire continues burning. Area empty of people. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `gunshot` = gunshot_visible + `explosion` = explosion_visible on VisualPerInterval.
- B: `gunshot` = gunshot + `explosion` = explosion on SoundPerInterval.
- C: `gunshot` = gunshot UNION gunshot_visible, `explosion` = explosion UNION explosion_visible.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Gunshot_visible + explosion_visible detected |
| B    | TP       | Gunshot + explosion detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | gunshot_or_explosion      |    4.000 |    4.375 |    96 | 105   | Gunshot with muzzle flash visible |
| audio    | gunshot_or_explosion      |    4.833 |    6.667 |   116 | 160   | Gas line explosion after gunshot |
| visual   | gunshot_visible           |    3.333 |    4.708 |    80 | 113   | Person holds gun, muzzle flash visible |
| visual   | explosion_visible         |    4.917 |    6.667 |   118 | 160   | Fireball, smoke, debris from gas explosion |
| visual   | running                   |    5.250 |    7.625 |   126 | 183   | People flee from explosion |

---


## Scene 8: Visible Drive-By Gunshot

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a street-side parking area. A few
pedestrians walk on the sidewalk. Normal activity, daytime.

2-3.5 seconds: A car approaches from off-camera left driving at moderate speed.
As it passes through the frame, a hand with a gun extends from the passenger
window. A muzzle flash is clearly visible. The gunshot sound is sharp and
distinct. The car continues driving and exits right.

3.5-5 seconds: Pedestrians react immediately: some duck, some run, some look
around in panic. One person falls to the ground, then gets up and runs.

5-8 seconds: People continue fleeing. The street becomes empty.

8-10 seconds: Empty frame. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `gunshot` = gunshot_visible on VisualPerInterval (muzzle flash) → TP.
- B: `gunshot` = gunshot on SoundPerInterval → TP.
- C: `gunshot` = gunshot UNION gunshot_visible → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Gunshot_visible detected (muzzle flash) |
| B    | TP       | Gunshot detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | gunshot_or_explosion      |    2.500 |    3.208 |    60 | 77    | Gunshot from passing car |
| visual   | gunshot_visible           |    2.625 |    2.917 |    63 | 70    | Hand with gun extended from car window, muzzle flash |
| visual   | running                   |    2.917 |    8.042 |    70 | 193   | Pedestrians flee in panic |

---



## Scene 9: Parking Lot Shooting

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot with several parked
cars. A person walks across the frame from left to right at a normal pace.

2-4 seconds: Another person steps out from between two parked cars, facing the
first person. An argument begins: shouting heard, arms waving.

4-5.5 seconds: The second person pulls out a handgun and fires a shot. The
muzzle flash is clearly visible. The gunshot sound is sharp and loud. Smoke
visible from the gun barrel.

5.5-8 seconds: The first person ducks and runs away. The shooter turns and runs
in the opposite direction. People in the background panic and flee.

8-10 seconds: The parking lot empties. One person is on the ground taking cover.
Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `gunshot` = gunshot_visible on VisualPerInterval (muzzle flash) → TP.
- B: `gunshot` = gunshot on SoundPerInterval → TP.
- C: `gunshot` = gunshot UNION gunshot_visible → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Gunshot_visible detected (muzzle flash) |
| B    | TP       | Gunshot detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | gunshot_or_explosion      |    4.750 |    5.750 |   114 | 138   | Gunshot with visible muzzle flash |
| visual   | gunshot_visible           |    4.458 |    5.917 |   107 | 142   | Person holding gun, muzzle flash visible |
| visual   | running                   |    5.250 |    6.958 |   126 | 167   | People flee in panic |

---

## Scene 10: Visible Warehouse Explosion

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of an industrial area with a warehouse
in the background. A truck is parked near the warehouse loading dock. A person
walks near the truck.

2-4 seconds: A massive explosion erupts from the warehouse: a large fireball,
thick black smoke billowing upward, debris flying through the air. The
explosion sound is a deep, powerful boom. Windows in nearby buildings shatter
audibly.

4-6 seconds: The person near the truck is thrown to the ground by the shockwave,
then gets up and runs. Debris continues to fall. The fire grows.

6-8 seconds: People run from all directions away from the warehouse. Sirens
begin to be heard in the distance. Smoke fills the frame.

8-10 seconds: The warehouse continues burning. Smoke billows. People have fled
the area. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `explosion` = explosion_visible on VisualPerInterval (fireball) → TP.
- B: `explosion` = explosion on SoundPerInterval → TP.
- C: `explosion` = explosion UNION explosion_visible → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Explosion_visible detected (fireball + debris) |
| B    | TP       | Explosion detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | gunshot_or_explosion      |    0.583 |    4.167 |    14 | 100   | Massive warehouse explosion |
| visual   | explosion_visible         |    0.667 |    4.167 |    16 | 100   | Fireball, smoke, flying debris |
| visual   | running                   |    2.958 |    9.667 |    71 | 232   | People flee from explosion |

---



## Scene 11: Car Fire Explosion

**Dreamina prompt (10 seconds, exact timing):**

0-3 seconds: Fixed security camera view of a parking lot. A parked car in the
center of frame has smoke rising from under the hood. A person nearby notices
and steps back.

3-5 seconds: The car erupts into a large fireball explosion: flames burst from
the hood, windows shatter, black smoke billows upward. The explosion sound is a
deep powerful boom. Debris flies in all directions.

5-7 seconds: The person who was nearby is thrown back by the shockwave, gets up
and runs. Other people in the area flee. The car continues burning.

7-10 seconds: The fire grows. Smoke fills the frame. People have fled. Sirens
heard in the distance. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `explosion` = explosion_visible on VisualPerInterval (fireball) → TP.
- B: `explosion` = explosion on SoundPerInterval → TP.
- C: `explosion` = explosion UNION explosion_visible → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Explosion_visible detected (fireball + smoke) |
| B    | TP       | Explosion detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | gunshot_or_explosion      |    1.542 |    4.167 |    37 | 100   | Car engine explosion |
| visual   | explosion_visible         |    1.667 |    5.000 |    40 | 120   | Fireball, smoke, debris from car explosion |
| visual   | running                   |    5.583 |    7.000 |   134 | 168   | People flee from explosion |

---

## Scene 12: Vehicle Escape

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot with a silver sedan
parked in the center. A person runs into frame from the right side, moving
quickly with urgency toward the car.

2-3.5 seconds: The person reaches the driver door, opens it, gets inside the car
quickly, and closes the door.

3.5-5 seconds: The car engine starts with a distinct engine starting sound. The
exhaust pipe emits visible smoke.

5-6.5 seconds: The car reverses sharply, backing up a short distance.

6.5-8 seconds: The car drives away fast to the left, disappearing off-frame. A
tire squeal sound is clearly audible as the car accelerates away.

8-10 seconds: The parking space where the car was parked is now empty. Static
surveillance camera angle, no movement.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_escape` = running SP enter_or_exit_vehicle on VisualPerInterval.
- B: `vehicle_escape` = engine SP tire_squeal on SoundPerInterval.
- C: `vehicle_escape` = (engine SP tire_squeal) UNION (running SP enter_or_exit_vehicle).

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects running + enter_vehicle chain |
| B    | TP       | Engine SP tire_squeal detected |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | engine                    |    3.875 |    5.500 |    93 | 132   | Car engine start |
| audio    | tire_squeal               |    5.500 |    8.667 |   132 | 208   | Tire squeal as car accelerates |
| visual   | running                   |    0.000 |    1.417 |     0 | 34    | Person runs toward parked car |
| visual   | enter_or_exit_vehicle     |    1.458 |    3.375 |    35 | 81    | Person enters car |

---


## Scene 13: Motorcycle Escape

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot with a motorcycle
parked near a building wall. A person approaches the motorcycle quickly,
looking around nervously.

2-3.5 seconds: The person straddles the motorcycle, inserts key, and starts the
engine. The motorcycle engine has a distinct high-rev starting sound.

3.5-5 seconds: The person revs the engine loudly, looks around once more.

5-7 seconds: The motorcycle accelerates away rapidly with a loud engine rev and
brief tire squeal as it exits the parking space.

7-10 seconds: The parking space is empty. The sound of the motorcycle fades in
the distance. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_escape` = running SP enter_or_exit_vehicle on VisualPerInterval.
- B: `vehicle_escape` = engine SP tire_squeal on SoundPerInterval.
- C: Same as scene 12: (engine SP tire_squeal) UNION (running SP enter_or_exit_vehicle).

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects running + enter_vehicle chain |
| B    | TP       | Engine SP tire_squeal detected (motorcycle) |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | engine                    |    3.958 |    7.875 |    95 | 189   | Motorcycle engine starting and revving |
| audio    | tire_squeal               |    7.875 |    9.083 |   189 | 218   | Tire squeal as motorcycle accelerates |
| visual   | running                   |    0.000 |    2.167 |     0 | 52    | Person approaches motorcycle quickly |
| visual   | enter_or_exit_vehicle     |    2.208 |    3.375 |    53 | 81    | Person mounts motorcycle |

---


## Scene 14: Diesel Truck Escape

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a loading dock area. A large diesel
delivery truck is parked near a warehouse door. A person in work clothes runs
from the warehouse toward the truck.

2-4 seconds: The person opens the truck door, climbs into the cab, and closes
the door.

4-6 seconds: The diesel engine starts with a loud rumble: distinct deep diesel
starting sound. Exhaust smoke visible from the vertical exhaust pipe.

6-7.5 seconds: The truck begins moving forward slowly, then accelerates.

7.5-9 seconds: As the truck turns, the tires produce a loud squeal on the
pavement. The truck drives away, exiting frame right.

9-10 seconds: The loading dock area is empty. Engine sound fades. Static
camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_escape` = running SP enter_or_exit_vehicle.
- B: `vehicle_escape` = engine SP tire_squeal.
- C: Same multimodal pattern.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects running + enter_vehicle chain |
| B    | TP       | Engine SP tire_squeal detected (diesel) |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | engine                    |    3.667 |    7.042 |    88 | 169   | Diesel engine starting and running |
| audio    | tire_squeal               |    7.042 |    9.167 |   169 | 220   | Truck tires squeal during turn |
| visual   | running                   |    0.000 |    1.792 |     0 | 43    | Person runs from warehouse to truck |
| visual   | enter_or_exit_vehicle     |    1.833 |    4.333 |    44 | 104   | Person enters truck cab |

---


## Scene 15: Vehicle Collision (Horn → Hit Parked Car)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot aisle with cars parked
on both sides. A car drives slowly down the aisle from left to right.

2-4 seconds: A pedestrian steps out from between parked cars into the path of
the moving car. The driver honks the horn loudly. The horn sound is distinct
and sustained. The pedestrian freezes.

4-5.5 seconds: The swerving car side-swipes a parked car, breaking its side
window. Loud glass breaking sound. The horn stops.

5.5-8 seconds: The moving car stops briefly. The pedestrian runs away. The
driver gets out to inspect the damage. Broken glass on the ground visible.

8-10 seconds: The driver gets back in the car. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_collision` = vehicle_collision on VisualPerInterval (damaged vehicle visible) → TP.
- B: `vehicle_collision` = (car_horn) SP (impact / glass_breaking) on SoundPerInterval → TP.
- C: `vehicle_collision` = sound query UNION visual within proximity → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects damaged vehicle |
| B    | TP       | Car horn SP impact/glass detects collision |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | horn                      |    0.792 |    3.042 |    19 | 73    | Driver honks horn |
| audio    | impact                    |    3.042 |    3.292 |    73 | 79    |  |
| audio    | glass_breaking            |    3.292 |    4.542 |    79 | 109   | Side window breaks |
| visual   | vehicle_collision         |    3.167 |   10.000 |    76 | 240   | Damaged parked car visible |

---


## Scene 16: Vehicle Collision (Skid → Storefront)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a street with storefronts on the
right side. A car drives along the street from left to right at moderate speed.

2-3.5 seconds: A dog runs into the street. The driver slams the brakes. Loud
tire skidding sound: tires locking and sliding on asphalt. The car skids
forward, leaving visible skid marks.

3.5-5 seconds: The car slides into a storefront window, shattering the glass.
Loud glass breaking sound. The car comes to a stop partially through the broken
window.

5-8 seconds: People on the sidewalk rush toward the crash. The driver sits still
in the car. Broken glass covers the ground. Visible damage to the storefront.

8-10 seconds: People gather around. The driver slowly opens the door. Static
camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_collision` = vehicle_collision on VisualPerInterval → TP (damaged storefront + car).
- B: `vehicle_collision` = (skidding) SP (impact / glass_breaking) on SoundPerInterval → TP.
- C: Both → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects crashed car into storefront |
| B    | TP       | Skid SP impact/glass detects collision |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | skidding                  |    1.292 |    2.208 |    31 | 53    | Tires skidding on asphalt |
| audio    | impact                    |    2.208 |    2.458 |    53 | 59    |  |
| audio    | glass_breaking            |    2.625 |    5.417 |    63 | 130   | Storefront window shatters |
| visual   | vehicle_collision         |    2.667 |   10.000 |    64 | 240   | Car embedded in storefront, broken glass |

---


## Scene 17: Vehicle Collision (Horn → Sideswipe)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a narrow alley between two
buildings. A car drives through the alley from foreground to background.

2-3.5 seconds: Another car enters unexpectedly from a side passage. The first
car honks loudly. Extended horn blast.

3.5-5 seconds: The cars collide side-to-side with a scraping sound and breaking
glass from a side mirror or window. The horn cuts off at impact. Glass
shattering sound.

5-7 seconds: Both cars stop. Drivers look at each other. One gets out to
inspect the damage. Scratches and broken glass visible on both vehicles.

7-10 seconds: Drivers exchange information. Camera remains static.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_collision` = vehicle_collision on VisualPerInterval → TP.
- B: `vehicle_collision` = (car_horn) SP (impact / glass_breaking) on SoundPerInterval → TP.
- C: Both → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects damaged vehicles |
| B    | TP       | Horn SP impact/glass detects collision |
| C    | TP       | UNION preserves both modalities |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | horn                      |    1.250 |    3.083 |    30 | 74    | Horn from first car |
| audio    | skidding                  |    2.208 |    3.083 |    53 | 74    |  |
| audio    | glass_breaking            |    3.083 |    4.583 |    74 | 110   | Side mirror/window breaks |
| visual   | vehicle_collision         |    3.042 |   10.000 |    73 | 240   | Two damaged cars after collision |

---


## Scene 18: Loitering (Suspicious Near Vehicle)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parked silver car in a parking lot.
A person approaches the car from the left at a normal walking pace. Footsteps
audible on the pavement.

2-7 seconds: The person stops at the driver side window, leans in close with
hands cupped around the eyes to peer inside the car. The person stays in this
position looking inside for about five seconds. Footsteps stop when the person
stops.

7-8.5 seconds: The person steps back from the car, looks around briefly to the
left and right.

8.5-10 seconds: The person walks away to the right at a normal pace. Footsteps
audible again as they leave. The parked car remains in frame. Static
surveillance camera angle.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `loitering` = suspicious_near_vehicle WITH duration >= delta_loitering [visual only].
- C: `loitering` = suspicious_near_vehicle WITH duration >= delta_loitering [visual only].

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | VLM detects peering into car >= 150 frames |
| C    | TP       | Visual-only query preserved |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | suspicious_near_vehicle   |    2.125 |    4.958 |    51 | 119   | Person peers into car window |

---


## Scene 19: Loitering (Crouching Near SUV)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot with a parked SUV in
the center. A person walks into frame from the left at a normal pace.

2-4 seconds: The person approaches the SUV and stops next to the driver side
door. They crouch down near the front tire, examining something on the ground or
the tire itself. The person stays crouched.

4-8 seconds: The person remains crouched next to the car for several seconds,
occasionally reaching out to touch the tire or look underneath. The person looks
around briefly, then returns attention to the car. This is clearly suspicious
behavior, inspecting the car up close.

8-10 seconds: The person stands up, looks around again, and walks away quickly,
exiting frame left. The SUV remains. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `loitering` = suspicious_near_vehicle WITH duration >= delta_loitering (150 frames). The person stays crouched near the car for ~6 seconds → TP.
- C: `loitering` = suspicious_near_vehicle WITH duration >= delta_loitering (same as visual) → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Person crouches near SUV >= 150 frames |
| C    | TP       | Visual-only query preserved |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | suspicious_near_vehicle   |    2.250 |    6.458 |    54 | 155   | Person crouches near SUV inspecting it |

---



## Scene 20: Loitering (Delivery Van)

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot with a delivery van
parked near a building. A person walks toward the van, looking around
nervously.

2-4 seconds: The person reaches the van and walks slowly around it, inspecting
it. The person peers into the driver window with hands cupped around the eyes.

4-7 seconds: The person tries the van's door handle. The door is locked. The
person walks to the back of the van and tries the rear handle. Clearly
suspicious behavior; this is not their vehicle.

7-8.5 seconds: The person steps back, looks around, then walks away quickly.

8.5-10 seconds: The person exits frame. The van remains. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `loitering` = suspicious_near_vehicle WITH duration >= delta_loitering (150 frames). Person inspects van for ~5 seconds → TP.
- C: `loitering` = suspicious_near_vehicle WITH duration >= delta_loitering (same as visual) → TP.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Person inspects delivery van >= 150 frames |
| C    | TP       | Visual-only query preserved |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | suspicious_near_vehicle   |    3.417 |    7.083 |    82 | 170   | Person inspects delivery van, tries door handles |

---

## Scene 21: Package Handoff

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a paved walkway in a parking lot.
Person A enters from the left side carrying a medium-sized cardboard box in both
hands, walking at a normal pace toward the center.

2-3.5 seconds: Person B enters from the right side walking at a normal pace,
also toward the center. Both approach each other.

3.5-5 seconds: They meet at the center of the frame. Person A holds the box out
and Person B reaches to take it. Person A lets go. Person B now holds the box.

5-7 seconds: Person B turns holding the box and walks away toward the right.
Person A turns empty-handed and walks away toward the left. Footsteps on
pavement are audible throughout.

7-10 seconds: Both persons exit on their respective sides. The walkway is empty.
Static surveillance camera angle, no zoom, no movement.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `handoff` = carrying(personA) BEFORE carrying(personB) on VisualPerInterval.
- C: Same as A (visual sequence carries detection).

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Carry(A) BEFORE carry(B) detected as handoff |
| C    | TP       | Visual-temporal detection preserved |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | carrying                  |    0.000 |    4.625 |     0 | 111   | Person A carries box toward center |
| visual   | carrying                  |    4.625 |    8.292 |   111 | 199   | Person B carries same box after handoff |

---


## Scene 22: Briefcase Handoff

**Dreamina prompt (10 seconds, exact timing):**

0-2.5 seconds: Fixed security camera view of a parking lot near a bench. Person
A walks from left carrying a briefcase in one hand, normal pace. Person B stands
near the bench, waiting.

2.5-4.5 seconds: Person A reaches Person B, stops, and hands the briefcase to
Person B. Person B takes the briefcase. Both people's hands are on the
briefcase momentarily during the transfer.

4.5-6 seconds: Person A turns and walks away left, empty-handed. Person B
clutches the briefcase and turns to walk right.

6-10 seconds: Both people exit frame on their respective sides. Area empty.
Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `handoff` = carrying(A) BEFORE carrying(B) on VisualPerInterval.
- C: Same as A.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Carry(A) BEFORE carry(B) detected as handoff |
| C    | TP       | Visual-temporal detection preserved |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | carrying                  |    0.417 |    5.500 |    10 | 132   | Person A carries briefcase |
| visual   | carrying                  |    5.000 |    9.750 |   120 | 234   | Person B carries briefcase after handoff |

---


## Scene 23: Three-Person Chain Handoff

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot walkway. Person A
enters from left carrying a small box. Person B stands in the middle of the
walkway. Person C stands near the right edge.

2-4 seconds: Person A reaches Person B and hands them the box. Person B takes
it. Person A turns and walks back left.

4-6 seconds: Person B walks toward Person C carrying the box, then hands it to
Person C. Person C takes the box. Person B turns and walks back toward the
center.

6-8 seconds: Person C turns and exits right carrying the box. Person A and
Person B have already exited or are leaving the frame.

8-10 seconds: The walkway is empty. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `handoff` = carrying(A) BEFORE carrying(B) BEFORE carrying(C).
- C: Same as A.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Two handoff events detected in chain |
| C    | TP       | Visual-temporal detection preserved |


**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | carrying                  |    0.000 |    2.583 |     0 | 62    | Person A carries box |
| visual   | carrying                  |    2.250 |    5.292 |    54 | 127   | Person B carries box |
| visual   | carrying                  |    4.833 |    7.208 |   116 | 173   | Person C carries box |

---


## Scene 29: Fight: Park Fight

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a park area with benches. Two people stand facing each other, arguing loudly.

2-4 seconds: The argument escalates. One person shoves the other. A physical fight breaks out, with pushing, shoving, and punching. Loud shouting throughout.

4-6 seconds: The fight continues with grappling and throwing punches. Shouting and impact sounds.

6-8 seconds: The two people separate. One backs away, still shouting.

8-10 seconds: One person exits frame left, the other exits right. Area becomes empty. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `fight` = physical_altercation on VisualPerInterval.
- B: `fight` = shout BEFORE impact on SoundPerInterval.
- C: `fight` = (shout BEFORE impact) UNION physical_altercation.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Physical altercation visible 2-8s |
| B    | TP       | Shout BEFORE impact detected |
| C    | TP       | UNION preserves both modalities |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | shout                     |    0.000 |    1.458 |     0 | 35    | Shouting during argument and fight |
| audio    | impact                    |    1.500 |    1.542 |    36 | 37    | Push impacts during fight |
| audio    | impact                    |    2.083 |    2.167 |    50 | 52    | Punch impacts during fight |
| visual   | physical_altercation      |    1.542 |    5.500 |    37 | 132   | Fighting, punching, shoving |
---

## Scene 30: Fight: Stairwell Fight

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of an indoor stairwell landing. Two people face each other, arguing loudly. Shouting clearly audible.

2-4 seconds: One person pushes the other against the wall. A physical fight breaks out, with punching and pushing. Loud shouting continues.

4-6 seconds: The fight continues with grappling. Punches thrown. Continued shouting.

6-8 seconds: A third person enters and shouts. The fighters separate.

8-10 seconds: The two fighters walk away. Stairwell becomes empty. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `fight` = physical_altercation on VisualPerInterval.
- B: `fight` = shout BEFORE impact on SoundPerInterval.
- C: `fight` = (shout BEFORE impact) UNION physical_altercation.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Physical altercation visible 2-7s |
| B    | TP       | Shout BEFORE impact detected |
| C    | TP       | UNION preserves both modalities |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | shout                     |    0.167 |    0.417 |     4 | 10    | Shouting throughout fight |
| audio    | impact                    |    0.417 |    5.083 |    10 | 122   | Punch impacts |
| visual   | physical_altercation      |    0.417 |    5.417 |    10 | 130   | Fighting, pushing, punching |
---

## Scene 31: Vehicle Escape: Parking Garage Getaway

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a concrete parking garage. A person runs toward a parked silver sedan.

2-4 seconds: The person opens the car door, gets inside, and closes the door.

4-6 seconds: The car engine starts. The car reverses out of the parking space.

6-8 seconds: The car accelerates forward with a loud tire squeal on the concrete.

8-10 seconds: The car drives away around the corner. The parking space is empty. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_escape` = running SP enter_or_exit_vehicle on VisualPerInterval.
- B: `vehicle_escape` = engine SP tire_squeal on SoundPerInterval.
- C: `vehicle_escape` = (engine SP tire_squeal) UNION (running SP enter_or_exit_vehicle).

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Running SP enter_or_exit_vehicle detected |
| B    | TP       | Engine SP tire_squeal detected |
| C    | TP       | UNION preserves both modalities |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | engine                    |    4.500 |    5.750 |   108 | 138   | Car engine starting and revving |
| audio    | tire_squeal               |    5.750 |   10.000 |   138 | 240   | Tire squeal on concrete |
| visual   | running                   |    0.000 |    1.875 |     0 | 45    | Person runs toward car |
| visual   | enter_or_exit_vehicle     |    1.958 |    4.042 |    47 | 97    | Person enters car |
---

## Scene 32: Vehicle Escape: Delivery Van Getaway

**Dreamina prompt (10 seconds, exact timing):**

0-3 seconds: Fixed security camera view of a parking lot in daylight. A person runs toward a parked delivery van.

3-5 seconds: The person opens the van door and gets inside.

5-7 seconds: The van engine starts. The van drives forward with a tire squeal.

7-10 seconds: The van drives away and exits frame. The parking lot is empty. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_escape` = running SP enter_or_exit_vehicle on VisualPerInterval.
- B: `vehicle_escape` = engine SP tire_squeal on SoundPerInterval.
- C: `vehicle_escape` = (engine SP tire_squeal) UNION (running SP enter_or_exit_vehicle).

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Running SP enter_or_exit_vehicle detected |
| B    | TP       | Engine SP tire_squeal detected |
| C    | TP       | UNION preserves both modalities |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | engine                    |    4.292 |    5.750 |   103 | 138   | Van engine starting and running |
| audio    | tire_squeal               |    5.750 |    7.583 |   138 | 182   | Tire squeal during acceleration |
| visual   | running                   |    0.000 |    2.000 |     0 | 48    | Person runs toward van |
| visual   | enter_or_exit_vehicle     |    2.042 |    4.125 |    49 | 99    | Person enters van |
---

## Scene 33: Vehicle Collision: Forward Collision with Horn

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot. A car drives forward down an aisle between parked cars.

2-4 seconds: The car approaches another car parked at the end of the aisle. A horn honks.

4-5 seconds: The car hits the parked car. Loud impact sound. Glass breaks from a headlight.

5-8 seconds: Both cars are stopped. Broken headlight visible. Broken glass on the ground.

8-10 seconds: Driver gets out to inspect. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_collision` = vehicle_collision on VisualPerInterval.
- B: `vehicle_collision` = (car_horn) SP (impact / glass_breaking) on SoundPerInterval.
- C: `vehicle_collision` = (horn SP impact/glass) UNION vehicle_collision.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Vehicle collision visible |
| B    | TP       | Horn SP impact/glass_breaking |
| C    | TP       | UNION preserves both modalities |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | horn                      |    1.167 |    2.583 |    28 | 62    | Horn blares before impact |
| audio    | glass_breaking            |    2.625 |    4.292 |    63 | 103   | Taillight breaking |
| visual   | vehicle_collision         |    2.625 |   10.000 |    63 | 240   | Damaged car with broken taillight |
---

## Scene 34: Vehicle Collision: Skidding Forward Collision

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot in daylight. A car drives forward down an aisle.

2-4 seconds: The car approaches a parked car. The car brakes suddenly with a skidding sound.

4-5 seconds: The car slides forward and hits the parked car. Loud impact sound. Glass breaks from a rear light.

5-8 seconds: Both cars stopped. Damage visible on the front of the moving car. Broken glass on ground.

8-10 seconds: Driver gets out to inspect. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `vehicle_collision` = vehicle_collision on VisualPerInterval.
- B: `vehicle_collision` = (skidding) SP (impact / glass_breaking) on SoundPerInterval.
- C: `vehicle_collision` = (skidding SP impact/glass) UNION vehicle_collision.

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Damaged side mirror visible |
| B    | TP       | Skidding SP impact/glass_breaking |
| C    | TP       | UNION preserves both modalities |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| audio    | skidding                  |    0.000 |    2.083 |     0 | 50    | Tires skidding before impact |
| audio    | glass_breaking            |    2.083 |    5.000 |    50 | 120   | Rear light breaking on impact |
| visual   | vehicle_collision         |    2.167 |   10.000 |    52 | 240   | Damaged cars after collision |
---

## Scene 35: Loitering: Person Inspecting Parked Car

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot. A silver car is parked near a building. A person approaches the car from the left at a normal walking pace.

2-7 seconds: The person stops at the driver side window, leans in close with hands cupped around the eyes to peer inside the car. The person stays in this position looking inside for about five seconds.

7-8.5 seconds: The person steps back from the car, looks around briefly.

8.5-10 seconds: The person walks away quickly, exiting frame. The car remains in frame. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `loitering` = suspicious_near_vehicle WITH duration >= delta [visual only].
- C: `loitering` = suspicious_near_vehicle WITH duration >= delta [visual only].

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Suspicious_near_vehicle for ~7s |
| C    | TP       | Visual-only query preserved |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | suspicious_near_vehicle   |    2.375 |    6.625 |    57 | 159   | Person peers into car, suspicious |
---

## Scene 36: Loitering: Person Inspecting Parked SUV

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a parking lot. A black SUV is parked near a building. A person approaches the SUV from the right at a normal walking pace.

2-7 seconds: The person stops at the driver side window and peers inside with hands cupped around the eyes. The person stays in this position for about five seconds, clearly inspecting the vehicle interior.

7-8.5 seconds: The person steps back, looks around, then tries the door handle.

8.5-10 seconds: The person walks away quickly, exiting frame. The SUV remains. Static surveillance camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `loitering` = suspicious_near_vehicle WITH duration >= delta [visual only].
- C: `loitering` = suspicious_near_vehicle WITH duration >= delta [visual only].

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Suspicious_near_vehicle for ~6.5s |
| C    | TP       | Visual-only query preserved |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | suspicious_near_vehicle   |    1.667 |    6.917 |    40 | 166   | Person peers into SUV, suspicious |
---

## Scene 37: Handoff: Backpack Exchange on Park Bench

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a walkway. Person A walks from left carrying a backpack in one hand. Person B stands near a bench on the right.

2-4 seconds: Person A reaches Person B and stops. Both people face each other.

4-6 seconds: Person A holds out the backpack. Person B reaches and takes it. Both persons' hands are on the backpack simultaneously.

6-8 seconds: Person B now holds the backpack. Person A turns and walks away left.

8-10 seconds: Person B puts on the backpack and walks away right. The area is empty. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `handoff` = carry(A) BEFORE/PRECEDES carry(B) WHERE A != B [visual only].
- C: `handoff` = carry(A) BEFORE/PRECEDES carry(B) [visual only].

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Carry(A) OVERLAPS carry(B) at ~4.5-6s |
| C    | TP       | Visual-temporal detection preserved |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | carrying                  |    0.000 |    5.083 |     0 | 122   | Person A carries backpack |
| visual   | carrying                  |    4.625 |   10.000 |   111 | 240   | Person B carries backpack after handoff |
---

## Scene 38: Handoff: Shopping Bag Handoff at Bus Stop

**Dreamina prompt (10 seconds, exact timing):**

0-2 seconds: Fixed security camera view of a bus stop. Person A walks into frame from the right carrying a shopping bag in one hand.

2-4 seconds: Person A stops near the bench. Person B approaches from the left and stops near Person A.

4-5 seconds: Person A extends the shopping bag. Person B reaches and takes it. Both hands are on the bag simultaneously.

5-6 seconds: Person B turns with the bag and walks away right. Person A walks away left.

6-10 seconds: The bus stop is empty. Static camera.

**Duration:** 10 seconds

**ISEQL pattern:**

- A: `handoff` = carry(A) BEFORE/PRECEDES carry(B) WHERE A != B [visual only].
- C: `handoff` = carry(A) BEFORE/PRECEDES carry(B) [visual only].

| Cond | Expected | Rationale |
| ---- | -------- | --------- |
| A    | TP       | Carry(A) OVERLAPS carry(B) at ~4.5-5s |
| C    | TP       | Visual-temporal detection preserved |



**Ground Truth:**

| Modality | Class | Start (s) | End (s) | Start Frame | End Frame | Description |
|----------|-------|-----------|---------|-------------|-----------|-------------|
| visual   | carrying                  |    0.000 |    5.167 |     0 | 124   | Person A carries shopping bag |
| visual   | carrying                  |    4.792 |    7.917 |   115 | 190   | Person B carries bag after handoff |
---

