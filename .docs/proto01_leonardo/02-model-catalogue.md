# 02 · Leonardo model catalogue, read against loom2

What the Production API v2 offers on 2026-10-08, and which of it matters to loom2. The tables in §3 are generated from the
mirrored OpenAPI definition (`tools/model_matrix.py`); §1–§2 are hand-written and must be re-read whenever the tables change.
Prices are not in the spec: the API returns the cost per job (01 §8), and the web app's pricing calculator is the only
up-front source.

## 1. How to read the spec

- One endpoint, `POST /v2/generations`, takes `{model, public, parameters}`; `model` is the discriminator and every model has
  its own parameter schema (79 of them). Model ids are **strings** (`flux-pro-2.0`, `kling-3.0`), not the UUIDs of v1.
- **Sizes** come in three shapes: free ranges (`64–14142 px` for FLUX.2 Pro), enumerated presets (GPT Image 2, every video
  model) and `0×0` = "derive from the start frame" (video). The enumerations are pairs: only listed width/height combinations
  validate, so loom2 must offer presets per model, not free fields.
- **Guidances** are the inputs. All take image references in one shape:
  `{"image": {"id" | "url" | "data", "type": UPLOADED | GENERATED | VARIATION | URL | BASE64}, "strength"?: LOW | MID | HIGH}`.
  The kinds that matter: `image_reference` (reference / instruction edit), `start_frame` + `end_frame` (video FLF),
  `video_reference_base` / `audio_reference` (omni models), and the legacy SDXL-family guidances
  (`style`, `content`, `character`, `edge`, `pose`, `depth`, `image_to_image`, `text_image`).
- **No v2 model takes a mask.** Inpainting exists only in the deprecated v1 canvas endpoints (SDXL-era). Every "edit" model is
  an instruction editor over whole reference images: Kontext, Nano Banana, GPT Image, Seedream, FLUX.2 Pro / FLUX 3 Image.
- `quantity` caps a request at 1–8 outputs; video, upscale and 3D are fixed at 1.
- `prompt_enhance: "ON" | "OFF"` exists on most models and rewrites the prompt server-side. loom2 should send `OFF` by
  default so that the recorded prompt is the prompt that ran (06 §5 provenance).
- `public` exists on every model and decides whether outputs appear in Leonardo's community feed. loom2 always sends `false`.

## 2. loom2 shortlist

Grouped by the loom2 verb they would serve. "Local counterpart" is what loom2 already runs on the RX 9070 XT; the cloud entry
is worth wiring where it adds something the 16 GB card cannot do, or does in minutes what local takes much longer to do.

### 2a. Generate (T2I, with references)

| Model id | Why it is on the list | Local counterpart |
| --- | --- | --- |
| `flux-pro-2.0` | same family as the local default (D21); up to 4 refs; free sizes up to 14142 px; seed. **Open:** whether the BFL JSON prompt passes through unchanged (prompt limit 9999 chars is enough) | `flux2-dev-fp8mixed` (≈ 60 s per draft, minutes at FHD) |
| `bfl/flux-3-image` | next FLUX generation, 10 refs; no seed in the schema | none |
| `gemini-image-2` (Nano Banana Pro), `nano-banana-2` | strongest reference following / text rendering; 6 refs | none |
| `gpt-image-2`, `openai/gpt-image-2.5-*` | text, layouts, `transparency` (alpha output); 6–16 refs; no seed | none |
| `seedream-5.0-pro`, `bytedance/seedream-5.0-flash` | 10 refs, PNG output option | none |
| `ideogram/ideogram-4.5` | typography; 5 refs | none |
| `lucid-origin`, `lucid-realism`, `phoenix-v1.0` | Leonardo's own models; cheap drafts | Klein 4B / 9B |

### 2b. Edit (instruction edit over a region, upscale, matte)

| Model id | loom2 use | Notes |
| --- | --- | --- |
| `flux-kontext-pro`, `flux-kontext-max` | "Instruct edit" on the cropped region, result pasted back through loom2's own feathered selection mask (03 §4) | 4 refs, seed |
| `gemini-image-2`, `nano-banana-2`, `gpt-image-2`, `seedream-4.5` | same verb, alternative editors | no mask: loom2's selection supplies the mask locally |
| `aurora-upscaler-precise` | Edit · Upscale "faithful" ×2 / ×3 / ×4 / ×6 / ×8, `upscale_mode` clean / detailed | local: Real-ESRGAN ×2/×4 + Klein tiled refine |
| `aurora-upscaler-creative` | Edit · Upscale "add detail", `creativity` | local: tiled refine (279 s cold, D31) |
| `remove-bg` | AI Select · Subject alternative; **sync** endpoint (≤ ≈ 27 s, result in the response) | local: BiRefNet (D33) |

### 2c. Animate (I2V, FLF, references)

| Model id | Start / end frame | Duration | Why |
| --- | --- | --- | --- |
| `hailuo-03` (**MiniMax H3**) | ✓ / ✓ | 5–15 s | **the D17 hero tier without local weights or the territorial licence application**; 480p–4K, audio, 9 image refs |
| `kling-3.0`, `kling-video-o-3` | ✓ / ✓ | 3–15 s | strong motion; O3 also edits a reference video |
| `veo-3.1-generate-001` (+ fast, lite) | ✓ / ✓ | 4 / 6 / 8 s | audio, 3 refs on the full model |
| `seedance-2.0` (+ fast, mini), `bytedance/seedance-2.5` | ✓ / ✓ | 4–15 s (2.5: 4–30 s) | references + audio; 2.5 takes 30 image refs |
| `alibaba/wan-3.0`, `wan-2.7` | ✓ / ✓ | 2–30 s / 2–10 s | same family as the local primary (Wan 2.2, D8) |
| `ltxv-2.3-pro`, `ltxv-2.3-fast` | ✓ / ✓ | 6–10 s / 6–20 s | same model as the local secondary (D9), at 1080p+ without streaming |

### 2d. Outside the current suites (recorded, not planned)

- **Audio** (`music-v1`, `sound-effects-v2`, `dialogue-v3`, `seed-audio-1.0`): TTS and music are MVP non-goals (03 §4); they
  belong to the Story workspace (14) when it reaches shots with sound.
- **3D** (`rodin-v2`, GLB, PBR, T/A pose): the gap the ArtCraft comparison noted (`../artcraft/07-loom2-comparison.md` §2).
- **Video edit** (`kling-video-o-3`, `wan-2.7` `omni_edit`, `bytedance/seedance-2.5` `omni_edit`) needs a video reference
  upload (`POST /v1/media`), a later slice.
- **Legacy SDXL family** (`kino-xl`, `anime-xl`, `concept-art`, …, `lightning-xl`): ControlNet-style guidances, but older than
  anything loom2 runs locally. Skip.

## 3. Full tables

<!-- matrix:start -->
Generated from `source/openapi-v2-creategeneration.json` (v2.0.0, 79 models) by `tools/model_matrix.py`.

### Image generation and reference editing (39)

| Model id | Title | Size | Max qty | Seed | Neg | Enhance | Styles | Guidances (max items) | Other parameters |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `flux-dev` | FLUX Dev | 480–2048 px | 8 | ✓ |  | ✓ | ✓ | style×1, content×1 | `user_elements`, `platform_elements` |
| `flux-kontext-pro` | FLUX.1 Kontext | 32–2048 px | 8 | ✓ |  | ✓ | ✓ | image_reference×4 | — |
| `flux-kontext-max` | FLUX.1 Kontext Max | 32–2048 px | 8 | ✓ |  | ✓ | ✓ | image_reference×4 | — |
| `flux-schnell` | FLUX Schnell | 32–2048 px | 8 | ✓ |  | ✓ | ✓ | style×1, content×1 | — |
| `flux-pro-2.0` | FLUX.2 Pro | 64–14142 px | 8 | ✓ |  | ✓ | ✓ | image_reference×4 | — |
| `phoenix-v0.9` | Phoenix 0.9 | 32–2048 px | 8 | ✓ | ✓ | ✓ | ✓ | style×4, content×1, character×1, image_to_image×1 | `mode` (FAST / QUALITY / ULTRA), `tiling`, `contrast` (LOW / MEDIUM / HIGH) |
| `phoenix-v1.0` | Phoenix 1.0 | 32–2048 px | 8 | ✓ | ✓ | ✓ | ✓ | style×4, content×1, character×1, image_to_image×1 | `mode` (FAST / QUALITY / ULTRA), `tiling`, `contrast` (LOW / MEDIUM / HIGH) |
| `kino-xl` | Cinematic Kino | 32–1536 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `anime-xl` | Anime | 32–1584 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `portrait-perfect` | Portrait Perfect | 32–1536 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `stock-photography` | Stock Photography | 32–1536 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `illustrative-albedo` | Illustrative Albedo | 32–1584 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `concept-art` | Concept Art | 32–1584 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `lifelike-vision` | Lifelike Vision | 32–1584 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `graphic-design` | Graphic Design | 32–1584 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `lightning-xl` | Leonardo Lightning | 32–1584 px | 8 | ✓ | ✓ | ✓ | ✓ | edge×1, pose×1, depth×1, style×4, content×1, character×1, text_image×1, image_to_image×1 | `mode` (FAST / QUALITY), `tiling`, `contrast` (LOW / MEDIUM / HIGH), `transparency`, `user_elements`, `platform_elements` |
| `ideogram-v3.0` | Ideogram 3.0 | 32–2048 px | 8 | ✓ | ✓ | ✓ | ✓ | — | `quality` (TURBO / BALANCED / QUALITY) |
| `ideogram-v4.0` | Ideogram 4.0 | listed pairs, ≤ 3328×3328 | 4 |  |  | ✓ |  | — | `quality` (TURBO / BALANCED / QUALITY) |
| `ideogram/p-image-ideogram` | P-Image-Ideogram | listed pairs, ≤ 3456×3456 | 8 |  |  | ✓ |  | — | `quality` (VERY_LOW / LOW / MEDIUM / HIGH) |
| `ideogram/ideogram-4.5` | Ideogram 4.5 | listed pairs, ≤ 3328×3328 | 8 | ✓ |  | ✓ |  | image_reference×5 | `quality` (VERY_LOW / LOW / MEDIUM / HIGH) |
| `gemini-2.5-flash-image` | Nano Banana | listed pairs, ≤ 1536×1344 | 8 | ✓ |  | ✓ | ✓ | image_reference×6 | — |
| `nano-banana-2` | Nano Banana 2 | listed pairs, ≤ 6336×5504 | 8 | ✓ |  | ✓ | ✓ | image_reference×6, video_reference_base×1 | — |
| `nano-banana-2-lite` | Nano Banana 2 Lite | listed pairs, ≤ 1584×1376 | 8 | ✓ |  | ✓ | ✓ | image_reference×6 | — |
| `gemini-image-2` | Nano Banana Pro | listed pairs, ≤ 6336×5504 | 8 | ✓ |  | ✓ | ✓ | image_reference×6 | — |
| `lucid-origin` | Lucid Origin | 16–3840 px | 8 | ✓ |  | ✓ | ✓ | style×1, content×1 | `mode` (FAST / ULTRA) |
| `lucid-realism` | Lucid Realism | 16–2496 px | 8 | ✓ |  | ✓ | ✓ | style×1, content×1 | `mode` (FAST / ULTRA) |
| `bfl/flux-3-image` | FLUX 3 Image | listed pairs, ≤ 6256×6256 | 8 |  |  | ✓ |  | image_reference×10 | — |
| `seedream-4.0` | Seedream 4.0 | 32–14142 px | 8 | ✓ |  | ✓ | ✓ | image_reference×6 | — |
| `seedream-4.5` | Seedream 4.5 | 32–14142 px | 8 | ✓ |  | ✓ | ✓ | image_reference×6 | — |
| `seedream-5.0-pro` | Seedream 5.0 Pro | 768–2048 px | 6 | ✓ |  | ✓ |  | image_reference×10 | `mode` (FAST / QUALITY), `output_format` (jpeg / png) |
| `bytedance/seedream-5.0-flash` | Seedream 5.0 Flash | 1024–3008 px | 8 |  |  | ✓ |  | image_reference×10 | `output_format` (jpeg / png) |
| `gpt-image-1.5` | GPT Image-1.5 | 1024–1536 px | 8 |  |  | ✓ | ✓ | image_reference×6 | `quality` (LOW / MEDIUM / HIGH), `transparency` |
| `gpt-image-2` | GPT Image 2 | listed pairs, ≤ 3808×3584 | 8 |  |  | ✓ | ✓ | image_reference×6 | `quality` (LOW / MEDIUM / HIGH), `transparency` |
| `openai/gpt-image-2.5-flare` | GPT Image 2.5 Flare | listed pairs, ≤ 3808×3584 | 8 |  |  | ✓ | ✓ | image_reference×16 | `quality` (LOW / MEDIUM / HIGH / XHIGH / MAX), `transparency` |
| `openai/gpt-image-2.5-sunburst` | GPT Image 2.5 Sunburst | listed pairs, ≤ 3808×3584 | 8 |  |  | ✓ | ✓ | image_reference×16 | `quality` (LOW / MEDIUM / HIGH / XHIGH / MAX), `transparency` |
| `recraft-v4` | Recraft V4 | listed pairs, ≤ 1536×1536 | 8 |  |  | ✓ |  | — | — |
| `recraft-v4-pro` | Recraft V4 Pro | listed pairs, ≤ 3072×3072 | 8 |  |  | ✓ |  | — | — |
| `krea-2-turbo` | Krea 2 Turbo | 16–4096 px | 8 |  |  | ✓ |  | — | — |
| `krea/krea-2` | Krea 2 | 16–4096 px | 8 | ✓ |  | ✓ |  | style×10 | `quality` (MEDIUM / HIGH) |

### Video generation (32)

| Model id | Title | Size | Duration | Audio | Seed | Guidances (max items) | Other parameters |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `motion_2.0` | Motion 2.0 | free | — |  | ✓ | start_frame×1 | `controls`, `elements`, `frame_interpolation` |
| `motion_2.0-fast` | Motion 2.0 Fast | free | — |  | ✓ | start_frame×1 | `controls`, `elements`, `frame_interpolation` |
| `veo-3.1-generate-001` | Veo 3.1 | listed pairs, ≤ 3840×3840 | 4 / 6 / 8 s | ✓ | ✓ | end_frame×1, start_frame×1, image_reference×3 | — |
| `veo-3.1-fast-generate-001` | Veo 3.1 Fast | listed pairs, ≤ 3840×3840 | 4 / 6 / 8 s | ✓ | ✓ | end_frame×1, start_frame×1 | — |
| `veo-3.1-lite` | Veo 3.1 Lite | listed pairs, ≤ 1920×1920 | 4 / 6 / 8 s | ✓ | ✓ | end_frame×1, start_frame×1 | — |
| `kling-2.5` | Kling 2.5 Turbo | free | 5 / 10 s |  |  | end_frame×1, start_frame×1 | — |
| `kling-2.6` | Kling 2.6 | listed pairs, ≤ 1920×1920 | 5 / 10 s | ✓ |  | start_frame×1 | — |
| `kling-2.5-turbo-standard` | Kling 2.5 Turbo Standard | free | 5 / 10 s |  |  | start_frame×1 | — |
| `ltxv-2.3-pro` | LTX-2.3 Pro | free | 6 / 8 / 10 s | ✓ |  | end_frame×1, start_frame×1 | — |
| `ltxv-2.3-fast` | LTX-2.3 Fast | free | 6–20 s | ✓ |  | end_frame×1, start_frame×1 | — |
| `happy-horse` | Happy Horse 1.0 | free | 3–15 s | ✓ | ✓ | start_frame×1, image_reference×9, video_reference_base×1 | `audio_setting` (auto / origin) |
| `happy-horse-1.1` | Happy Horse 1.1 | free | 3–15 s | ✓ | ✓ | start_frame×1, image_reference×9 | — |
| `hailuo-2_3` | Hailuo 2.3 | listed pairs, ≤ 1920×1920 | 6 / 10 s |  |  | start_frame×1 | — |
| `hailuo-2_3-fast` | Hailuo 2.3 Fast | listed pairs, ≤ 1920×1920 | 6 / 10 s |  |  | start_frame×1 | — |
| `hailuo-03` | MiniMax H3 | listed pairs, ≤ 5040×3840 | 5–15 s | ✓ |  | end_frame×1, start_frame×1, audio_reference×3, image_reference×9, video_reference_base×3 | `quality` (STANDARD / ACCELERATED / TURBO), `resolution` (480p / 768p / 2k / 4k) |
| `alibaba/wan-3.0` | Wan 3.0 | listed pairs, ≤ 1920×1920 | 2–30 s | ✓ | ✓ | end_frame×1, start_frame×1, audio_reference×5, image_reference×10, webpage_reference×1, video_reference_base×5 | `quality` (STANDARD / ACCELERATED), `resolution` (480p / 720p / 1080p) |
| `wan-2.7` | Wan 2.7 | listed pairs, ≤ 1920×1920 | 2–10 s |  |  | end_frame×1, start_frame×1, image_reference×6, video_reference_base×1 | `omni_edit`, `resolution` (720p / 1080p) |
| `bfl/flux-3-video` | FLUX 3 Video | listed pairs, ≤ 2520×1920 | 5–20 s | ✓ |  | end_frame×1, start_frame×1, video_reference_base×1 | `resolution` (720p / 1080p) |
| `wan-2.6` | Wan 2.6 | listed pairs, ≤ 1920×1920 | 5 / 10 / 15 s |  | ✓ | start_frame×1, audio_reference×1, video_reference_base×3 | `resolution` (720p / 1080p) |
| `seedance-1.0-pro` | Seedance 1.0 Pro | free | 4–10 s |  | ✓ | end_frame×1, start_frame×1 | — |
| `seedance-1.0-pro-fast` | Seedance 1.0 Pro Fast | free | 4–10 s |  | ✓ | start_frame×1 | — |
| `seedance-2.0` | Seedance 2.0 | free | 4–15 s | ✓ | ✓ | end_frame×1, start_frame×1, audio_reference×1, image_reference×4, video_reference_base×3 | — |
| `seedance-2.0-fast` | Seedance 2.0 Fast | free | 4–15 s | ✓ | ✓ | end_frame×1, start_frame×1, audio_reference×1, image_reference×4, video_reference_base×3 | — |
| `seedance-2.0-mini` | Seedance 2.0 Mini | free | 4–15 s | ✓ | ✓ | end_frame×1, start_frame×1, audio_reference×1, image_reference×4, video_reference_base×3 | — |
| `bytedance/seedance-2.5` | Seedance 2.5 | free | 4–30 s | ✓ | ✓ | end_frame×1, start_frame×1, audio_reference×10, image_reference×30, video_reference_base×10 | `omni_edit` |
| `grok-imagine-1.5` | Grok Imagine 1.5 | listed pairs, ≤ 1888×1888 | 3–15 s | ✓ |  | start_frame×1 | — |
| `kling-video-o-1` | Kling O1 Video Model | ?–2160 px | — |  |  | end_frame×1, start_frame×1, image_reference×5, video_reference_base×1 | — |
| `kling-3.0` | Kling Video 3.0 | listed pairs, ≤ 3840×3840 | 3–15 s | ✓ |  | end_frame×1, start_frame×1 | — |
| `kling-3.0-turbo` | Kling 3.0 Turbo | listed pairs, ≤ 1920×1920 | 3–15 s | ✓ |  | start_frame×1 | — |
| `gemini-omni-flash` | Gemini Omni Flash | listed pairs, ≤ 1280×1280 | 3–10 s |  |  | image_reference×5 | — |
| `google/gemini-omni-1.1-flash-preview` | Gemini Omni 1.1 Flash | listed pairs, ≤ 3840×3840 | 3–10 s | ✓ |  | end_frame×1, start_frame×1, image_reference×10, video_reference_base×3 | — |
| `kling-video-o-3` | Kling Video O3 Omni | ?–3840 px | 3–15 s | ✓ |  | end_frame×1, start_frame×1, image_reference×7, video_reference_base×1 | — |

### Upscale and background removal (3)

| Model id | Title | Size | Guidances (max items) | Other parameters |
| --- | --- | --- | --- | --- |
| `aurora-upscaler-creative` | Aurora Upscaler Creative | 128–? px | image_reference×1 | `priority`, `creativity` (low / mid / high), `upscale_factor` (2 / 3 / 4 / 6 / 8) |
| `aurora-upscaler-precise` | Aurora Upscaler Precise | 128–? px | image_reference×1 | `priority`, `upscale_mode` (clean / detailed), `upscale_factor` (2 / 3 / 4 / 6 / 8) |
| `remove-bg` | Remove Background | — | image_reference×1, background_image_reference×1 | `roi`, `crop`, `size` (auto / preview / full / 50MP), `type`, `scale`, `format` (png / jpg / webp), `bg_color`, `channels` (rgba / alpha), `position`, `type_level` (none / 1 / 2 / latest), `crop_margin`, `shadow_type` (none / drop / 3d / car), `shadow_opacity`, `semitransparency` |

### Audio (4)

| Model id | Title | Max qty | Duration | Guidances (max items) | Other parameters |
| --- | --- | --- | --- | --- | --- |
| `music-v1` | Music | 4 | — | — | `duration_minutes`, `force_instrumental` |
| `sound-effects-v2` | Sound Effects | 4 | 1–22 s | — | `loop`, `prompt_influence` |
| `dialogue-v3` | Dialogue | 4 | — | — | `voice_id`, `language_code`, `prompt_influence` |
| `seed-audio-1.0` | Seed Audio 1.0 | 4 | — | audio_reference×3, image_reference×1 | `pitch`, `speed`, `volume`, `voice_id`, `language_code` (en) |

### 3D (1)

| Model id | Title | Guidances (max items) | Other parameters |
| --- | --- | --- | --- |
| `rodin-v2` | Rodin V2 | image_reference×5 | `quality` (extra_low / low / medium / high), `ta_pose`, `material` (PBR / Shaded / All), `mesh_mode` (Quad / Triangle), `bounding_box`, `output_format` (glb), `use_original_alpha` |
<!-- matrix:end -->

## 4. Deprecation cadence

`source/docs/deprecations-changes.md` lists five retirements between 2026-04-20 and 2026-07-09, usually with **2 to 4 weeks'**
notice: Sora 2 / 2 Pro retired outright, Motion 1.0, Veo 3, Veo `-preview` aliases, Seedance 1.0 Lite, the `mode` parameter of
GPT Image 1.5 / Ideogram 3.0. Consequences for loom2 are in 03 §6: model ids live in data, not code; the mirror is re-run at
each milestone start (as for 04 §8's volatile facts); a retired id fails with a readable message and old assets keep their
recorded model id.
