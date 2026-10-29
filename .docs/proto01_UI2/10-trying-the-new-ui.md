# 10 · Trying the new UI (for the author)

About 30 minutes. Each GPU step is optional and marked ⚙; it queues one job, one at a time (D97).

The new UI is built (D157, waves U0–U8). It has four layers in the work's order: **World · Shots · Episode · Bin**. It runs beside today's UI
on the same records. ☰ › **Try the new UI** opens it and ☰ › **Back to the current UI** returns; the page reloads, and nothing is lost
between them.

This is your click-through. Your notes decide what changes before the new UI becomes the default and the old shell is removed (U8). Hover
a small **?** for its words.

Start with `scripts/dev.ps1`. Open a **copy** of a project you know (The Last Ferry is good), or a new one.

## 1. World — what the story is made of (≈ 6 min)

- The rail is **Characters · Props · Places · Look · Sketches**. Pick a character. The header shows the entity, its version, *See in clay ▶*
  and its readiness. Each owed item there is its verb: ✓ hero, references, A-pose front / back, body fitted, voice.
- The left column is **Make · Edit · Clay**:
  - **Make** makes pictures for this version only: the framing chips, the look, the model, the count. ⚙ *Give Ines a look ▶*.
  - **Edit** opens the selected picture in the editor. Save puts the result back into this version's bin.
  - **Clay** (*See in clay ▶*) is the version's bench inside World. A character stands as its figure, a prop at its height beside a 1.75 m
    figure, a place as its set.
- The centre is the version's **bin**: one grid, its roles as badges (★ hero, ref, A-pose), and chips to filter by role. A tile's
  right-click makes it the hero, a reference or a candidate.
- The Inspector, with nothing selected, gives the entity's facts: the shots that use it (a click opens one), its versions, its voice, and
  *Delete…*.
- **Look** holds the project's style. **Sketches** holds free pictures and imports for the brainstorm; *Bring the ideas in* turns them into
  entities.
- **Check:** is Make / Edit / Clay the right split? Do you miss anything from Cast, Image or the Catalogue here?

## 2. Shots — one shot from Flow to Final (≈ 10 min)

- **The storyboard** sits across the top: the route's shots in order, each with three dots, Clay · Performance · Final (✓ done, ○ owed,
  ! stale).
- **The rail** is the shot's levels: **Flow · Clay · Performance · Final**.
- **Flow:** today's canvas. A double-click on a node opens its shot.
- **The shot's header:**
  - its scene (one clay stage per scene), its camera and its range;
  - the cast with each one's readiness;
  - the **words**: what the shot's pictures are prompted with, from its scene, cast, light and the shot itself.
- **Clay:** the scene's stage at the shot's camera.
  - The figures' tracks hold **clip blocks**: drag one from the Library onto a figure.
  - A block can be dragged, trimmed, looped, baked and saved as an animation; layer keys inside it are corrections.
  - Lines and *facing away* have rows of their own.
- **Performance:** the method card. *Final shot* (layered) is the default; the others are *Stage clip* and *Image to video*. The
  speaking close-up has no card yet (Story's *Lip-sync ▶* today).
  - The method is kept on the shot's record.
  - The For chip is this shot's version.
  - ⚙ *Perform the owed layers ▶* queues the plate and each character layer not performed yet, with the minutes.
  - A figure seen from behind is performed from behind (D158).
- **Final:** the shot's own final.
  - The **Voice and lip-sync** section lays the shot's lines on the lanes by themselves. ⚙ Each speaking character has *Lip-sync ▶*.
  - Each character layer shows its identity (FaceSim).
  - ⚙ Render. Then *Mark the shot final ✓*.
- **Check:**
  - Does every level open where you expect, on the shot's stage and camera?
  - Is the method card clear?
  - Are the words right, and editable enough?
  - Is *To Final ▸* where you want it?

## 3. Episode — the shots' finals cut together (≈ 7 min)

- **The left column:**
  - **Finals**, the route's shots in order, each with its final (✓ rendered, ○ not yet, ! stale) and a *final* chip when the shot is
    marked final. A click opens that shot at Final.
  - Then the **Cuts**, the **Shots** and the **Clips**.
  - **Sound**, the project's sounds; + places one on Music at the playhead.
- **Assemble from the Flow…:**
  - The sheet counts the route: *4 shots on this route · 2 without a final (left out): …*.
  - It lays each shot's final: the version marked final, else the latest final. A shot made in one pass (stage clip, start still) counts
    its clip.
  - Clips are named after their shots.
  - A shot whose lines run longer than it is held for them when its final has the frames. Otherwise the checklist lists it.
- Change something: trim a shot, slow it, grade it. Then render a newer final for one shot, ⚙ or just mark one final. Then **Assemble
  again…**:
  - only what changed is placed;
  - your edits to the rest stay;
  - the whole Assemble is one undo step.
- A 16 fps take conforms to 24 fps by RIFE as it lands (a small CPU job, one undo step). The cut refreshes when it is done.
- Everything else is today's editor: the tools, dissolves, sound, VST3, colour, captions, *Export for Resolve ▶*, *Render the movie*.
- **Check:**
  - Is "finals only" the right rule? A shot without a final is left out.
  - Is the Finals list useful above the cuts?

## 4. Bin — every creation in its home (≈ 4 min)

- **The left:** a search (prompt, name, tag or seed) and the tree of homes with counts:
  - World's entity versions, the Look and the Sketches;
  - the shots and their versions;
  - the cuts;
  - **Imports**, the things that belong to nothing yet;
  - the Trash.
- **The centre:** the home's grid, everything below it for a parent, with role badges and the kind chips. A double-click or *See it
  large* shows a thing large; Esc closes it.
- **The Inspector:** its home, roles, how it was made and its run. *Open where it belongs ▸* (its version in World, its shot, its cut),
  *Move to…*, *Tag…*, *Trash*, and *Detach ↗*, a window that follows the selection.
- **The drawer:** in World, Shots and Episode the Dock's **Bin** tab is the same homes in a drawer. Its tiles have today's verbs: a
  double-click does the likely one, a right-click lists them all, and a tile drags to wherever it is used.
- **Check:**
  - Is the tree's order right?
  - Should Imports be sorted by you, or is it fine as it is?
  - Do you miss the Library or Unprocessed?

## 5. What is not there yet

- Compare in the Bin. Today's Catalogue compare is not in the new Bin; the large view and *Detach ↗* are.
- Q8: Episode's closed lists (a duration field, FilmCraft's other transitions).
- A music bed across a shot that Assemble must take off blocks the Assemble (FilmCraft's sync rule). Move the bed first.
- The rig owes: Final's lip-sync pass in the new shell, and the speaking close-up's own card.

When you are done, say which of the checks you would change. Say also whether the new UI can become the default, with the old shell removed
after it (U8's last two steps).
