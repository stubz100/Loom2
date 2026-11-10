<!-- markdownlint-disable MD013 -->
# 04 · Questions for the author

Written 2026-11-10. Each question changes what a wave builds. The recommendation is what [01](01-application.md) and [03](03-plan.md) assumed
until answered. The column *Asks* says which wave waits on it.

**Answered the same day — see [06](06-answers.md)** (seven against the recommendation: Q2 strictly one scene per shot, Q3 the 20 s cap kept, Q6b the copy's
scope chosen per copy, Q8 free clips in Sketches, Q9 Process | Final as two modes, Q12 the experiments kept, Q21 Expand kept; Q22 in the author's words; follow-ups Q2b and Q6b). This page is kept as
it was asked.

## The shape

| # | Question | Options | Recommendation | Asks |
| --- | --- | --- | --- | --- |
| **Q1** | **The top rail's order.** | (a) World · Clay · Shots · Episode · Bin, as now; (b) World · Shots · Clay · Episode · Bin — the overview before the bench | (a): it is the order of the work (World's assets, then the shots built from them), and Shots is reached from Clay's shot rail anyway | RS4 |
| **Q2** | **Coverage.** A scene and a shot are created together (your rule). May one scene still serve several shots — the same blocking seen by a second camera, a dialogue's shot and reverse — or is it strictly one scene per shot? | (a) a scene serves one or more shots, each its own camera and range; a new scene always makes its first shot, the last shot's delete deletes the scene; (b) strictly one each: *another angle* copies the scene, and later edits do not carry over | (a): it keeps D157 Q2 / D181 Q3 as you answered them, the blocking made once, and every scene still has a shot and every shot a scene | RS3 |
| **Q3** | **The scene's length cap.** You remembered 15 s; the record (D181 Q4) and the code say **5 s default, 20 s cap**. | (a) lower the cap to 15 s; (b) keep 20 s | (a) if 15 s is what you want: every 5 s past the first is one more chained window of Wan Animate / LTX and one more join, and nothing in the code depends on 20. A scene already longer keeps its length but cannot grow. | RS3 |
| **Q4** | **The shot rail on top of Clay** ("a simple graph of the shots, visible and selectable"). | (a) the Flow's shots as a thin graph, branches drawn as forks, the logic nodes as small unlabelled diamonds; (b) the route's shots in a straight row, like the storyboard strip; (c) the whole Flow, every node labelled, as a minimap | (a): it shows where the story forks without the Flow's detail; the Flow itself stays in Shots | RS4 |
| **Q5** | **Animations and poses.** A character's own poses go to World › Clay with the character; the animation workshop (D182) stays in Clay as a rail item beside the shot. | (a) yes; (b) both in World; (c) both in Clay | (a): a pose is fitted to one character's body (D141); an animation is the scene's material, retargeted to whoever plays it | RS1, RS4 |
| **Q11** | **Episodes.** You wrote "a full assembly bench for each episode". Is a project one episode, or does it hold several? | (a) a project is one episode (one Flow, one cut per route, as now); (b) a project holds episodes, each its own Flow and cut, sharing World | (a) for proto02: it is how the records are built today; (b) is a study of its own if you want a series in one project | RS5 |

## Process

| # | Question | Options | Recommendation | Asks |
| --- | --- | --- | --- | --- |
| **Q6** | **A copied chain** ("copy these processing chains to other shots … to keep an episode coherent"). | (a) a snapshot: the steps and settings copied; changing the source later changes nothing else; copy again to update; (b) linked: shots share one chain, each may override a step; a change to the chain re-stales every shot that uses it | (a) first: simpler, nothing goes stale behind your back; the copy remembers its source so *Update from ‹shot›* can come later if you want (b) | RS7 |
| **Q8** | **No clip without clay.** Image to video today takes any picture in the Bin; H3, LTX and Fun-Camera likewise; S2V any picture. Under your rule only a still that descends from the shot's clay may start a clip. Is there any place left for a clip from a free picture (a mood test in Sketches, say)? | (a) none anywhere; (b) only in World › Sketches, never in a shot | (a): the rule is simplest when it has no exception; a mood test is a shot with a quick clay | RS6 |
| **Q9** | **Performance and Final in Process.** | (a) one chain view: Source → Still → Generate → Passes → Composite → Output, the compositor opening as Composite's editor in the centre; (b) two modes, Process \| Final, as Performance and Final are now | (a): one list of steps is what can be copied (Q6) and what says what is stale; the compositor stays whole as a step's editor | RS6 |
| **Q12** | **The two experimental clip-only steps** (D88): *Speaking* — the S2V talking close-up, English only, ≤ 4.8 s, in the record but not in the method menu; *Extend* — a clip continued past its end by its own model. | (a) keep both as Generate steps marked experimental; (b) drop both (lip-sync stays a pass; a shot's length comes from its clay) | (b): both invent motion the clay did not decide, against your rule for Process | RS6 |
| **Q7** | **New v2v models.** Every step the chain needs exists. Should a spike look for a plainer "redraw the animatic" v2v (E65: Wan 2.2 VACE / Fun-Control on the pinned engine's core nodes; downloads approved first), or the clip upscaler again (E66)? | (a) after RS7, on your word; (b) now, before RS6; (c) not at all | (a): the chain first, with the models measured; a new model is then one more tile on a step | RS6 |

## The rules

| # | Question | Options | Recommendation | Asks |
| --- | --- | --- | --- | --- |
| **Q13** | **Where a run form sits** (G2: every generation shows its parameters). | (a) inline in the column above its ▶, as Make's and the Still's are; (b) a sheet that ▶ opens, then Run | (a): display == reality (T8) — what will run is on screen before the click, and mouse-first means no hidden second step | RS2 |
| **Q16** | **What a run form remembers.** | (a) per thing: the shell's settings on the character version, a step's on the shot; (b) the last used, everywhere | (a): a copied chain (Q6) and a re-run must find their own settings | RS2 |
| **Q18** | **Your own saved presets** — Image to video presets, the field presets behind icons, stage templates, shot templates, saved poses. They are made with the tool's commands, so they pass G1. | (a) keep them working as they are, no new work (G3); (b) hide them until the templating study | (a): nothing is lost and nothing is added; the study decides their future | RS8 |
| **Q10** | **"Scene" means two things** — Clay's scene (a stage) and the Flow's scene group (`scn_*`, with words of its own that go into the shots' prompts). | (a) rename the Flow's group *sequence* (a run of shots in one place and time); (b) fold its words into each shot and drop the group | (a): its words are shared by its shots and worth keeping; the name is the film term | RS3 |

## The details

| # | Question | Options | Recommendation | Asks |
| --- | --- | --- | --- | --- |
| **Q14** | **D196** (the shell's sole and leg stance) is built and tested but not committed; your look in Clay is owed. | (a) commit it as it is before RS0; (b) look first, then commit | (a): proto02's waves move the files it touches (the skeleton bench, `CastBody`); starting on a clean tree keeps its diff readable | RS0 |
| **Q15** | **A place's crowd and walkers** (D173, D174) are loops made from the set's own faces. | (a) with the place in World › Clay, the set builder; (b) with the shot in Clay, as scene material | (a): they are made from the place and reused by every shot there; a shot places and times them | RS1 |
| **Q17** | **Shot versions** stay in Clay's shot header (a version holds its process and final, pins the scene's revision; the scene is one per shot, with its own undo). | (a) yes; (b) a version also copies the scene, so two blockings can live side by side | (a): *Duplicate shot* covers a second blocking | RS4 |
| **Q19** | **The lines** (dialogue, voiced by the character's voice). | (a) a Lines track in Clay's tracks, the line's editor (words, voice, *Voice again*) in the Inspector; (b) a section in the shot's column | (a): a line has a time in the shot, as a clip block has | RS4 |
| **Q20** | **The line-up** (several characters or props side by side at their sizes). | (a) keep it, from World's class rail (right-click, several picked); (b) drop it | (a): it is the one place sizes are compared; it costs a menu item | RS1 |
| **Q21** | **Leftovers of D157** ("Expand and LoRA training are taken out altogether"): Expand is still reached through Image's Poses section in World › Sketches; *Train a LoRA…* through the palette (Ctrl+K); the old Ideas board's *Make the clay ▶* is dead code. | (a) remove all three; (b) keep Expand in Sketches as a free tool | (a): they are what D157 decided against, reached by accident through reused parts | RS8 |
| **Q22** | **The stage's preset sets and stand-ins** — the sets *room · street · deck · empty* and the stand-ins *crate · stool · table · pole · block* are fixed geometry; nothing in loom2 can model them (G1). | (a) remove the preset sets (a set is a World place's) and keep only *block* and *pole* as plain shapes with their sizes as fields; (b) remove all of them (a stand-in is a World prop); (c) keep them | (a): a box and a pole sized by hand are the scene's own commands, as a cube is a 3D tool's; a table or a street is a thing World should make | RS8 |
