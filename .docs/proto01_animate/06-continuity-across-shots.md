# 06 · Continuity across Shots — options

Status: **options for the author, 2026-10-18.** Nothing decided.

The author (2026-10-18): *"[We] will probably have to introduce shot templates and object copying, so two shots in the same environment
would look the same. Let's write down a few options to solve this."*

## 1. The problem

One camera per Shot (D96) means a scene is several Shots: shot / reverse-shot in a dialogue, a wide shot and its close-ups. They must
match:

- the **set** (the same walls, furniture, window), seen from other angles;
- the **light** (direction, colour, time of day) and the shadows;
- the **characters** (face, costume, hair) and the **props**, in the same state (a glass half full stays half full);
- the **colour** of the finished frames.

Each Shot is generated separately, so without help each one drifts on its own: E21's stills changed a jacket from yellow to olive, and
every plate generation reinvents a little of the room.

## 2. What already holds things together

- **Cast versions** pin a character's look and costume. Profiles and versions (D93 B) bind colours on the sheet, and Flow nodes pin
  speaker versions.
- **One stage, many cameras:** a stage holds the set; several cameras can look at it (Stage's cameras, ST3).
- **The World style** and the Look presets are shared by the project.
- **The animation reference** (CA0) is one image per character version, used by every Shot.

What is missing: a place where the *shared* parts of a scene live, a way to make a new Shot *from* another, a way to copy objects with
or without a link, and a check that tells when Shots drift apart.

## 3. Options

### O1 · A Scene record that Shots link to

A **Scene** (the Flow's scene group, D96) owns what its Shots share, **by reference, not by copy**:

- the stage's set and its props;
- the plate look (the hero plate, §O4);
- the key light;
- the World style;
- the Cast versions in the scene (costumes at this point of the story);
- the props' states;
- a colour grade (an EffectCraft adjustment preset applied to every Shot's composition).

Each Shot's recipe (05) then *links* these steps instead of holding its own copies. Change the light once and every Shot of the scene
marks its plate, layers and take stale; *Run stale* re-makes them.

- **For:** one truth per scene, and staleness works across Shots for free (the recipe's stamps).
- **Against:** a new record, and a Shot moved to another scene must re-link.

### O2 · Shot templates: "New Shot from this Shot"

A new Shot starts as a copy of an existing Shot's **recipe**:

- the scene-level steps stay **linked** (O1);
- the Shot-level steps (camera, motion, lines, performance settings) are **copied** as independent starting points;
- the author can flip any step between linked and copied.

**Saved templates** are the same thing kept in the World Library (D92), like ComfyUI's workflow templates: *"Dialogue · shot /
reverse-shot pair"*, *"Walk-in wide shot"*, *"Close-up from the wide"*.

- **For:** fast, and consistent by construction.
- **Against:** the link / copy choice per step must be visible, or it surprises.

### O3 · Object copying, linked or independent

For anything a Shot uses (a stage object, a prop, a plate, a composition's layer or effect stack, a grade) there are two kinds of copy,
as in 3D tools (Blender's linked duplicate vs duplicate):

- **Linked copy:** one object used in two places. Edit it once and both change; *Make independent* breaks the link.
- **Independent copy:** a separate object from the moment of copying (the Catalogue's *Duplicate*, D34, keeps working this way).

The Catalogue's one-place rule holds: a linked object is **one** item with several users (*used by* shows them); an independent copy is a
second item.

- **For:** general; the same mechanism serves sets, props, grades and effect stacks.
- **Against:** linked copies need care in the UI (a badge, the users list).

### O4 · Lock the look when generating

Make the generations themselves agree:

- **A hero plate per set:** the first plate of a scene becomes the **reference** for the plates of its other cameras (Klein with
  references: the same room, seen from elsewhere), with the same seed and the World style.
- **The animation reference** is the same image per character version in every Shot (CA0): faces and costumes come from one source.
- **Costume colours bound** on the sheet (D93 B), passed to every still and keyframe still.
- **The key light** lives on the set, so every Shot's shadow pass and plate prompt agree on its direction.

- **For:** prevents drift instead of repairing it.
- **Against:** a plate from a very different angle can still invent new parts of the room. The stage's blocks keep the geometry, the
  reference keeps the materials.

### O5 · A continuity check

A check across the Shots of a scene that flags drift:

- the background's colour statistics on matching regions;
- FaceSim per character against its animation reference;
- the costume colour in the bound regions;
- the light direction from the shadow pass;
- a prop's look against its reference.

It is shown on the scene group in the Flow ("Shot 14: Ines's jacket differs") with a fix to try: re-run with the hero plate, a healing
patch (A6), or a grade match.

- **For:** catches what slips through.
- **Against:** metrics need tuning, so it should be advisory, like Validate today.

### O6 · Match in the cut

In the cut editor (the FilmCraft-like suite, RC4):

- a **grade per scene**;
- a **shot-match** tool that matches a Shot's colour to a reference Shot of the same scene.

The last line of defence, for colour only.

### O7 · State over story time

Things that change during the story (a torn sleeve, a glass emptied, night falling) are **versions**:

- a costume version (D93 B), a prop version, the scene's light.
- The Flow's order is story time; the Scene record (O1) pins the versions valid in that scene, so the next scene can move on without
  breaking this one.

## 4. A suggested combination

| Layer | Options | When |
| --- | --- | --- |
| The model | **O1** Scene record + **O3** linked / independent copies | with the recipe record (RC0) and the Shot node (RC2) |
| Speed | **O2** templates ("New Shot from this Shot", saved templates in the Library) | with RC2 |
| Prevention | **O4** hero plate as reference, one animation reference, bound colours, the key light on the set | with CA0, CA2, CA3 |
| Detection | **O5** the continuity check | after the first scenes are made, in the Story pass |
| Repair | A6 healing patch, **O6** scene grade and shot-match in the cut | with AE4; with RC4 |
| Story time | **O7** versions pinned per scene | with O1 (versions exist) |

## 5. Questions for the author

1. Is **O1** (a Scene that owns the shared parts, Shots link to it) the model you want, or do you prefer copies with templates (O2)
   alone?
2. **Linked by default:** within a scene, should a new Shot link the shared parts (O1 / O3), with *Make independent* to break away?
3. **O5:** is an advisory continuity check welcome, or only the visual comparison?
