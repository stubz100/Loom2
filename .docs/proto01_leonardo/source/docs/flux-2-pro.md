---
updatedAt: 2026-01-22T05:33:37.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# FLUX.2 Pro

This guide shows how to generate images using FLUX.2 Pro model via the Leonardo.AI REST API.

This guide shows how to generate images using **FLUX.2 Pro** model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "public": false,
       "model": "flux-pro-2.0",
       "parameters": {
           "prompt": "A cat wearing a hat",
           "quantity": 1,
           "width": 1440,
           "height": 1440,
           "seed": 4294967295,
           "guidances": {
               "image_reference": [
                  {
                      "image": {
                          "id": "fc6f78c6-e7ac-491b-ad26-01f6843db870",
                          "type": "GENERATED"
                      },
                      "strength": "MID"
                  },
                  {
                      "image": {
                          "id": "a8e374dd-52f8-4236-ad9e-99b1f601fa3a",
                          "type": "UPLOADED"
                      },
                      "strength": "MID"
                  }
              ]
           }
        }
      }'
```

# Recipe

<Recipe slug="generate-with-flux-pro-20-model-using-uploaded-image" title="Generate with FLUX.2 Pro Model Using Uploaded Image" />

# API Request Endpoint, Headers, Parameters (FLUX.2 Pro)

## Endpoint

```curl
https://cloud.leonardo.ai/api/rest/v2/generations
```

## Headers

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                  | Type      | Definition                                                                                                                                                    |
| :------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                        |
| guidances.image\_reference | `array`   | *Optional.* Array of up to 4 reference images. Each reference includes image.id, image.type (`GENERATED` or `UPLOADED`), and strength (`LOW`, `MID`, `HIGH`). |
| height                     | `integer` | *Optional.* Height input resolution. Supports `256` to `1440`.                                                                                                |
| model                      | `string`  | *Required.* Model identifier. Set to `flux-pro-2.0`                                                                                                           |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate.                                                                                 |
| prompt\_enhance            | `string`  | *Optional.* Enables prompt enhancement when set to `"ON"`; disabled when set to `"OFF"`.                                                                      |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                      |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request. Default is 1, maximum is 8.                                                                     |
| seed                       | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets. The maximum seed value is `4294967295` for Flux.                               |
| style\_ids                 | `array`   | *Optional.* Array of style UUIDs used to apply preset artistic styles to the output.                                                                          |
| width                      | `integer` | *Optional.* Width input resolution. Supports `256` to `1440`.                                                                                                 |

## Aspect Ratio Settings

| Aspect Ratio | Width | Height |
| :----------- | :---- | :----- |
| 2:3          | 960   | 1440   |
| 1:1          | 1440  | 1440   |
| 16:9         | 1440  | 810    |
| 9:16         | 810   | 1440   |

<br />