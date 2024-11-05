
# VPX Tool Installation and Usage Guide

## Overview
**VPX** is a command-line tool for RTL (Register Transfer Level) development tasks, leveraging AI to assist with design, debugging, and documentation of RTL modules. VPX enables a structured design approach using the `vpx implement` command to guide an AI model through a systematic thought process.

### Key Commands
- `vpx implement <instructions>`: Implements RTL modules based on high-level design instructions.
- `vpx document <module_path.sv>` (coming soon): Generates module documentation.
- `vpx debug <module_path.sv>` (coming soon): Detects and suggests fixes for RTL modules.

---

## Installation Steps

### Step 1: Install VPX Using pipx

To install VPX, use `pipx`, which ensures isolated dependencies. Run:

```bash
pipx install vpx
```

### Step 2: Log In to VPX

Once installed, log in to activate your license:

```bash
vpx login
```

When prompted, enter:
- **Your email address**
- **Your license key**

### Troubleshooting

- **Command Not Found**: Verify `pipx` installation and ensure it’s in your PATH.
- **Login Issues**: Check that the correct email and license key are used and confirm internet connectivity.
- **Dependency Issues**: Reinstall VPX using `pipx reinstall vpx` if needed.
---

## Using the `vpx implement` Command

The `vpx implement` command guides an AI model through a structured thought process for RTL design. This breakdown outlines the LLM’s design approach and thought steps for implementing a complex FSM-based module.

### Command:

```
vpm implement

"""I would like you to implement a module named TopModule with the following interface. All input and output ports are one bit unless otherwise specified.

 - input  clk
 - input  areset
 - input  bump_left
 - input  bump_right
 - input  ground
 - input  dig
 - output walk_left
 - output walk_right
 - output aaah
 - output digging

The game Lemmings involves critters with fairly simple brains. So simple that we are going to model it using a finite state machine. In the
Lemmings' 2D world, Lemmings can be in one of two states: walking left (walk_left is 1) or walking right (walk_right is 1). It will switch directions if it hits an obstacle. In particular, if a Lemming is bumped
on the left (by receiving a 1 on bump_left), it will walk right. If it's bumped on the right (by receiving a 1 on bump_right), it will walk left. If it's bumped on both sides at the same time, it will still switch
directions.

In addition to walking left and right and changing direction when bumped, when ground=0, the Lemming will fall and say ""aaah!"". When the ground reappears (ground=1), the Lemming will resume walking in the same direction as before the fall. Being bumped while falling does not affect the walking direction, and being bumped in the same cycle as ground disappears (but not yet falling), or when the ground reappears while still falling, also does not affect the walking direction.

In addition to walking and falling, Lemmings can sometimes be told to do useful things, like dig (it starts digging when dig=1). A Lemming can dig if it is currently walking on ground (ground=1 and not falling), and will
continue digging until it reaches the other side (ground=0). At that point, since there is no ground, it will fall (aaah!), then continue walking in its original direction once it hits ground again. As with falling, being bumped while digging has no effect, and being told to dig when falling or when there is no ground is ignored. (In other words, a walking Lemming can fall, dig, or switch directions. If more than one of these conditions are satisfied, fall has higher precedence than dig, which has higher precedence than switching directions.)

Although Lemmings can walk, fall, and dig, Lemmings aren't invulnerable. If a Lemming falls for too long then hits the ground, it can splatter. In particular, if a Lemming falls for more than 20 clock cycles then hits the ground, it will splatter and cease walking, falling, or digging (all 4 outputs become 0), forever (Or until the FSM gets reset). There is no upper limit on how far a Lemming can fall before hitting the ground. Lemmings only splatter when hitting the ground; they do not splatter in mid-air.

Implement a Moore state machine that models this behaviour. areset is positive edge triggered asynchronous reseting the Lemming machine to walk left.

Assume all sequential logic is triggered on the positive edge of the clock.
"""
```

### Internally, our agent follow's this step-by-step thought process:

#### **1. Define the Module Interface**
   - **Goal**: Define inputs and outputs according to user instructions.
   - **Example Interface**:
     - **Inputs**: `clk`, `areset`, `bump_left`, `bump_right`, `ground`, `dig`
     - **Outputs**: `walk_left`, `walk_right`, `aaah`, `digging`

#### **2. Identify and Define Storage Elements (State and Counters)**
   - **State Register**: Define states as an enumerated type or constants.
     - States: `WALK_LEFT`, `WALK_RIGHT`, `FALL_LEFT`, `FALL_RIGHT`, `DIG_LEFT`, `DIG_RIGHT`, `SPLAT`
   - **Counter**: Define `fall_count` to track time in the FALL state. If `fall_count` exceeds 20 cycles, the Lemming transitions to the `SPLAT` state when ground returns.

#### **3. Determine Combinational Logic Paths**
   - **Objective**: Define the logic for state transitions and output generation.
   - **Paths**:
     - **State Transition Logic**:
       - Uses inputs: `ground`, `bump_left`, `bump_right`, `dig`, and `fall_count`.
       - **Priority**: FALL has the highest priority, DIG is next, followed by direction changes.
     - **Output Generation**:
       - `walk_left`, `walk_right`, `aaah`, and `digging` are driven by the current state.

#### **4. Timing Diagram Analysis**
   - **Purpose**: Confirm correct behavior across cycles. The timing diagram below shows the progression of `ground`, `bump_left`, `dig`, `state`, `fall_count`, and outputs:
   ```plaintext
   Clock     |‾|_|‾|_|‾|_|‾|_|‾|_|‾|_|‾|_|
   ground    |1|1|0|0|0|0|1|1|1|1|1|1|1|1|
   bump_left |0|0|0|0|0|0|0|1|0|0|0|0|0|0|
   dig       |0|0|0|0|0|0|0|0|1|1|0|0|0|0|
   state     |WL|WL|FL|FL|FL|FL|WL|WR|DG|DG|FL|FL|WL|WL|
   
   fall_cnt  |0|0|1|2|3|4|0|0|0|0|0|1|0|0|
   walk_left |1|1|0|0|0|0|1|0|0|0|0|0|1|1|
   walk_right|0|0|0|0|0|0|0|1|0|0|0|0|0|0|
   aaah      |0|0|1|1|1|1|0|0|0|0|1|1|0|0|
   digging   |0|0|0|0|0|0|0|0|1|1|0|0|0|0|
   ```

#### **5. Compact Finite State Machine (FSM) Representation**
The following ASCII diagram summarizes state transitions and conditions in a compact FSM notation:

```
          WALK_LEFT ---------- bump_left=1 ----------> WALK_RIGHT
              |                                         |
  ground=0    |                                         |   ground=0
              v                                         v
          FALL_LEFT <------------ bump_right=1 ------- WALK_RIGHT
              |                                         |
   dig=1,     |                                         |   dig=1,
 ground=1     v                                         | ground=1
 ------------> DIG_LEFT                               DIG_RIGHT <----------
              |                                         |                |
    ground=0  v                                         v ground=0       |
 ------------ FALL_LEFT <-------- bump_right=1 ------- FALL_RIGHT       SPLAT
              |                   ground=1, fall_count > 20
              v
           SPLAT (All outputs = 0)
```

**Transitions**:
- **FALL**: Occurs if `ground=0` (highest priority).
- **SPLAT**: Transitions upon ground return if `fall_count > 20`.
- **DIG**: Transitions when `dig=1` and `ground=1` (overrides direction changes).
- **Direction Change**: Triggers on `bump_left` or `bump_right` (lowest priority).

**Outputs**:
- `walk_left`: Asserted in `WALK_LEFT`.
- `walk_right`: Asserted in `WALK_RIGHT`.
- `aaah`: Asserted in `FALL_LEFT` and `FALL_RIGHT`.
- `digging`: Asserted in `DIG_LEFT` and `DIG_RIGHT`.
- **SPLAT**: Forces all outputs to zero.

---

## Using the `vpx document` Command

Documents an RTL module given either a) RTL code, or b) natural language.

Coming soon.

## Using the `vpx debug` Command

Debugging assistance. Ranges from displaying logic cones, to generating timing diagrams and testbenches, to autonomous RTL debugging.

Coming soon.
---
