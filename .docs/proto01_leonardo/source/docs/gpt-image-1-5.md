---
updatedAt: 2026-06-29T01:25:04.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# GPT Image-1.5

This guide shows how to generate images using GPT Image-1.5 model via the Leonardo.AI REST API.

<Callout icon="⚠️" theme="warn">
  ###

  Deprecation Notice – mode parameter The mode parameter is being deprecated and will no longer be supported from May 4, 2026. Please update your requests to use the quality parameter instead. After May 4th, any requests that include mode will return a validation error and fail. What you need to do: Replace 'mode' with 'quality' in your API requests for GPT 1.5 and Ideogram generations before May 4th to avoid service disruption.

  You can find the migration example in [Deprecations & Changes](https://docs.leonardo.ai/docs/deprecations-changes#april-20-2026--mode-parameter-retiring-may-4-2026) page
</Callout>

This guide shows how to generate images using the GPT Image-1.5 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --location 'https://cloud.leonardo.ai/api/rest/v2/generations' \
     --header 'authorization: Bearer {api-key}' \
     --header 'Content-Type: application/json' \
     --data '{
       "public": false,
       "model": "gpt-image-1.5",
       "parameters": {
           "quality": "MEDIUM",
           "prompt": "Koala with purple hat",
           "quantity": 2,
           "width": 1024,
           "height": 1024,
           "seed": 4294967295,
           "prompt_enhance": "OFF"
           "guidances": {
               "image_reference": [
                   {
                       "image": {
                       "id": "00000000-0000-0000-0000-000000000001",
                       "type": "UPLOADED"
                       },
                       "strength": "MID",
                   }
               ]
           }
        }
     }'
```

# Recipe

<Recipe slug="generate-with-gpt15-model-using-uploaded-image" title="Generate with GPT1.5 Model Using Uploaded Image" />

# API Request Endpoint, Headers, Parameters

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
| guidances.image\_reference | `array`   | *Optional.* Array of up to 6 reference images. Each reference includes image.id, image.type (`GENERATED` or `UPLOADED`), and strength (`LOW`, `MID`, `HIGH`). |
| height                     | `integer` | *Optional.* Height input resolution.                                                                                                                          |
| model                      | `string`  | *Required.* Model identifier. Set to `gpt-image-1.5`                                                                                                          |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate.                                                                                 |
| prompt\_enhance            | `string`  | *Optional.* Enables prompt enhancement when set to `"ON"`; disabled when set to `"OFF"`.                                                                      |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                      |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request.                                                                                                 |
| seed                       | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets.                                                                                |
| width                      | `integer` | *Optional.* Width input resolution.                                                                                                                           |
| quality                    | `string`  | *Optional.* Accepts `LOW`, `MEDIUM`, or `HIGH`.                                                                                                               |

### Aspect Ratio Settings

| Aspect Ratio | Width | Height |
| :----------- | :---- | :----- |
| 2:3          | 1024  | 1536   |
| 1:1          | 1024  | 1024   |
| 3:2          | 1536  | 1024   |

<br />

<br />