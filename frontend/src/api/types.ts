// The API's types (D38): re-exported from schema.d.ts, which openapi-typescript generates from the orchestrator's OpenAPI
// document (scripts/export_openapi.py → npm run api:types). Never hand-edit a response shape here — change the pydantic model
// in orchestrator/loom2 (schemas.py or the record's own module) and regenerate. Only UI-side types live below the line.
import type { components } from './schema'

/** openapi-fetch hands every reply through its Readable<…> (tuples become arrays); mirroring it keeps these types equal to what
 *  `unwrap(http.GET(…))` returns, so a reply can be stored wherever its type is expected. */
type Readable<T> = T extends (infer E)[] ? Readable<E>[] : T extends object ? { [K in keyof T]: Readable<T[K]> } : T
type S = { [K in keyof components['schemas']]: Readable<components['schemas'][K]> }

export type HealthInfo = S['HealthInfo']
export type VersionInfo = S['VersionInfo']
export type Capabilities = S['Capabilities']
export type Final = S['Final']                          // D111 (PS5): the final shot
export type FinalLayer = S['FinalLayer']
export type Composition = S['Composition']              // AE1 (D114): the final's EffectCraft composition
export type TeOption = S['TeOption']                    // D31
export type I2vCaps = S['I2vCaps']
export type I2vModelCaps = S['I2vModelCaps']
export type ImageModelCaps = S['ImageModelCaps']          // D65: generated from the model specs
export type ToolCaps = S['ToolCaps']
export type SampleModelCaps = S['SampleModelCaps']        // D91: Settings › Samples › Sample model
export type VideoPreset = S['VideoPreset']
export type ProjectFormat = S['ProjectFormat']
export type ProjectInfo = S['ProjectInfo']
export type EngineState = S['EngineState']
export type QueueState = S['QueueState']
export type Job = S['JobRecord']
export type Asset = S['AssetRecord']
export type Clip = S['ClipRecord']
export type Timeline = S['Timeline']                          // P17 (D83): a sequence document
export type TimelineClipIn = S['TimelineClip']
export type CutTracks = S['CutTracks']                        // CE2 (D126, proto01_animate 30 §12): a FilmCraft cut's every track
export type CutTrack = S['CutTrack']
export type CutItem = S['CutItem']
export type CutTransition = S['CutTransition']
export type CutEdited = S['CutEdited']
export type TrackStrip = S['TrackStrip']                      // D127: an audio track's gain, volume, pan and width (Settings › Audio holds one per role)
export type TrackRole = NonNullable<CutTrack['role']>
export type CutEffect = S['CutEffect']                        // AU4 (D127): a VST3 effect in an audio track's chain
export type VstPlugin = S['VstPlugin']                        // an installed effect loom2's host can run (GET /audio/plugins)
export type VstPluginList = S['VstPluginList']
export type CutGrade = S['CutGrade']                          // CE4 (O6): a clip's colour as its Lumetri holds it
export type ColourLooks = S['ColourLooks']                    // FilmCraft's presets and built-in looks
export type ModelEntry = S['ModelEntry']
export type FetchState = S['FetchState']
export type UnlistedFile = S['UnlistedFile']
export type Settings = S['Settings']
export type EngineSettings = S['EngineSettings']
export type EventFrame = S['EventFrame']
export type Recipe = S['Recipe']

// ---- UI-side types (not API shapes) ---------------------------------------------------------------------------------
export type Suite = 'catalogue' | 'generate' | 'edit' | 'animate' | 'stage' | 'final' | 'story' | 'models'   // D121: Animate's levels — stage (Clay), animate (Performance), final (Final)
export type StageDoc = S['Stage']                              // P13 / ST1 (D81): a 3D blocking document
export type StageObject = S['StageObject']
export type StageCamera = S['StageCamera']
export type StageTemplate = S['StageTemplate']                  // D119 (SC2): an arrangement of the Clay level saved under a name
export type StageTemplates = S['StageTemplates']
export type World = S['World']                                // 17 (D85): the Story world (L1)
export type WorldStyle = S['StoryStyle']
export type Library = S['Library']                            // D92: the World library of prompt-field presets
export type LibraryEntry = S['LibraryEntry']
export type SavedPanel = S['SavedPanel']                      // D92: Generate's saved panel, with its picture
export type StoryBeat = S['StoryBeat']
export type StoryVariable = S['StoryVariable']
export type Profile = S['Profile']                            // 17 (D85) SY1: a character, place or prop with versions
export type LoraRecord = S['LoraRecordOut']                  // 18 (D86) LT2: a LoRA the project trained
export type TrainCaps = S['TrainCaps']
export type VoiceRecord = S['VoiceRecordOut']                // 19 (D87) CN2: a voice of the project
export type VoiceCaps = S['VoiceCaps']
export type ProfileVersion = S['ProfileVersion']
export type Shot = S['Shot']                                  // 17 (D85) SY2: a shot with versions
export type ShotVersion = S['ShotVersion']
export type CastUse = S['CastUse']                            // D125 (S5): a shot that uses a Cast profile, how and its route
export type CastReadiness = S['CastReadiness']
export type FlowNode = S['FlowNode']                          // 17 (D85) SY3: the flow
export type FlowGraph = S['FlowGraph']
export type FlowOption = S['FlowOption']
export type FlowProblem = S['FlowProblem']
export type JobStatus = Job['status']
export type Health = ModelEntry['health']

export interface Backend { host: string; port: number; token: string }

// ---- recipe preview (POST /recipes/preview answers per recipe kind) --------------------------------------------------
export type T2IPreview = S['T2IPreview']
export type Binding = S['BindingOut']                         // D93 (A3): a linked subject and the reference images its mention gave
export type ProfileAdded = S['ProfileAdded']                  // D93 (A2): Add to character ▸ — what moved, what was copied
export type I2VPreview = S['I2VPreview']
export type DocumentPreview = S['DocumentPreview']
export type AnyPreview = T2IPreview | I2VPreview | DocumentPreview          // D64: /recipes/preview plans every kind
export const isI2VPreview = (p: AnyPreview): p is I2VPreview => 'frames' in p && 'family' in p
export const isT2IPreview = (p: AnyPreview): p is T2IPreview => 'serialized_prompt' in p
export const isDocumentPreview = (p: AnyPreview): p is DocumentPreview => 'needs' in p && 'engine' in p
export type GroupHeader = S['GroupHeader']
export type AssetPage = S['AssetPage']
export type AlbumNode = S['AlbumNode']
export type GroupPage = S['GroupPage']
export type GroupSummary = S['GroupSummary']
export type GroupItem = S['GroupItem']
export type PathStep = S['PathStep']
export type GroupLocation = S['Location']
export type GroupUser = S['GroupUser']                    // D92 §4.2: what uses a group (GET /groups/used-by)
export type LineageTree = S['LineageTree']
export type Document = S['Document']
export type DocumentPutReply = S['DocumentPutReply']
export type DocSummary = S['DocSummary']

// ---- recipes as the panels build them (request input: fields with defaults are optional) -----------------------------
type In = components['schemas']
export type T2IRecipe = In['T2I']
export type I2IRecipe = In['I2I']
export type InpaintRecipe = In['Inpaint']
export type UpscaleRecipe = In['Upscale']
export type SegmentRecipe = In['Segment']
export type RefineEdgeParams = In['RefineEdge']            // D45
export type I2VRecipe = In['I2V']
export type DocumentRecipe = InpaintRecipe | I2IRecipe | UpscaleRecipe | SegmentRecipe
/** D66: where a job was started (`POST /jobs` body `origin`); `Job.origin`, `Asset.origin` and `clip.ready` echo it back. */
export type JobOrigin = In['JobOrigin-Input']

// ---- WebSocket event payloads the suites handle ----------------------------------------------------------------------
export type DocumentChangedData = S['DocumentChanged']
export type ClipReadyData = S['ClipReady']
export type ClipUpdatedData = S['ClipUpdated']
