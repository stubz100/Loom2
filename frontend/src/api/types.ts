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
export type TeOption = S['TeOption']                    // D31
export type I2vCaps = S['I2vCaps']
export type I2vModelCaps = S['I2vModelCaps']
export type ProjectFormat = S['ProjectFormat']
export type ProjectInfo = S['ProjectInfo']
export type EngineState = S['EngineState']
export type QueueState = S['QueueState']
export type Job = S['JobRecord']
export type Asset = S['AssetRecord']
export type Clip = S['ClipRecord']
export type ModelEntry = S['ModelEntry']
export type FetchState = S['FetchState']
export type UnlistedFile = S['UnlistedFile']
export type Settings = S['Settings']
export type EngineSettings = S['EngineSettings']
export type EventFrame = S['EventFrame']
export type Recipe = S['Recipe']

// ---- UI-side types (not API shapes) ---------------------------------------------------------------------------------
export type Suite = 'catalogue' | 'generate' | 'edit' | 'animate' | 'models'
export type JobStatus = Job['status']
export type Health = ModelEntry['health']

export interface Backend { host: string; port: number; token: string }

// ---- recipe preview (POST /recipes/preview answers per recipe kind) --------------------------------------------------
export type T2IPreview = S['T2IPreview']
export type I2VPreview = S['I2VPreview']
export const isI2VPreview = (p: T2IPreview | I2VPreview): p is I2VPreview => 'frames' in p && 'family' in p
export const isT2IPreview = (p: T2IPreview | I2VPreview): p is T2IPreview => 'serialized_prompt' in p
export type GroupHeader = S['GroupHeader']
export type AssetPage = S['AssetPage']
export type AlbumNode = S['AlbumNode']
export type GroupPage = S['GroupPage']
export type GroupSummary = S['GroupSummary']
export type GroupItem = S['GroupItem']
export type PathStep = S['PathStep']
export type GroupLocation = S['Location']
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

// ---- WebSocket event payloads the suites handle ----------------------------------------------------------------------
export type DocumentChangedData = S['DocumentChanged']
export type ClipReadyData = S['ClipReady']
export type ClipUpdatedData = S['ClipUpdated']
