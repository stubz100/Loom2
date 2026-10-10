---
updatedAt: 2026-06-23T05:28:21.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Rodin V2

This guide shows how to generate 3D assets using the Rodin V2 model via the Leonardo.AI REST API.

# Sample Request

```cURL
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "model": "rodin-v2",
  "public": false,
  "parameters": {
    "quantity": 1,
    "output_format": "glb",
    "mesh_mode": "Quad",
    "quality": "high",
    "material": "PBR",
    "seed": 12345,
    "ta_pose": true,
    "bounding_box": [100, 200, 100],
    "use_original_alpha": true,
    "guidances": {
      "image_reference": [
        {
          "image": {
            "id": "00000000-0000-0000-0000-000000000001",
            "type": "GENERATED"
          },
          "strength": "HIGH"
        },
        {
          "image": {
            "id": "00000000-0000-0000-0000-000000000002",
            "type": "UPLOADED"
          },
          "strength": "MID"
        }
      ]
    }
  }
}
'
```

# Recipe

# API Request Endpoint, Headers, Parameters

## Endpoint

```cURL
https://cloud.leonardo.ai/api/rest/v2/generations
```

## Headers

```cURL
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                   | Type    | Definition                                                                                                                                                                                                             |
| --------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bounding_box`              | array   | Bounding box dimensions as `[width, height, length]`. Must contain exactly 3 integers. Used to constrain the generated model size.                                                                                     |
| `guidances.image_reference` | array   | Reference images of the character or object from different angles. Minimum 1 item, maximum 5 items. Each item includes `image.id`, `image.type` (`GENERATED` or `UPLOADED`), and `strength` (`LOW`, `MID`, or `HIGH`). |
| `material`                  | string  | Material mode for the generated mesh. Valid values are `PBR` (physically based materials), `Shaded` (baked shading), and `All` (both). Default is `All`.                                                               |
| `mesh_mode`                 | string  | Type of faces in the generated mesh. Valid values are `Quad` (quadrilateral faces, smoother surfaces) and `Triangle` (triangular faces, more detailed geometry). Default is `Triangle`.                                |
| `model`                     | string  | Specifies the model used for generation. Set to `rodin-v2`.                                                                                                                                                            |
| `output_format`             | string  | Mesh file format for the generated 3D asset. Set to `glb`.                                                                                                                                                             |
| `public`                    | boolean | Controls whether the generated asset is public (`true`) or private (`false`).                                                                                                                                          |
| `quality`                   | string  | Generation quality level. Valid values are `extra_low`, `low`, `medium`, and `high`. Default is `high`. Polygon counts depend on `mesh_mode` (see Constraints).                                                        |
| `quantity`                  | integer | Number of assets generated per request. Set to `1`.                                                                                                                                                                    |
| `seed`                      | integer | Seed for reproducible generation. Range: `0`–`65535`.                                                                                                                                                                  |
| `ta_pose`                   | boolean | Applies a T/A-pose constraint for human character meshes, making the result easier to rig and animate. Default is `false`.                                                                                             |
| `use_original_alpha`        | boolean | Preserves the original alpha channel from input images. Default is `false`.                                                                                                                                            |

## Constraints

* `guidances.image_reference` accepts between 1 and 5 reference images per request.
* `quantity` is fixed at `1`. Only a single asset is generated per request.
* `output_format` is fixed at `glb`.

<br />

| `mesh_mode` | `extra_low` | `low` | `medium` | `high` |
| ----------- | ----------- | ----- | -------- | ------ |
| `Triangle`  | 2k          | 20k   | 150k     | 500k   |
| `Quad`      | 4k          | 8k    | 18k      | 50k    |

<br />