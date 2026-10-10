---
updatedAt: 2026-07-09T11:00:16.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedream 5.0 Pro

This guide shows how to generate images using the Seedream 5.0 Pro model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "seedream-5.0-pro",
       "parameters": {
           "width": 2048,
           "height": 2048,
           "prompt": "Koala with purple wizard hat on a skateboard",
           "quantity": 2,
           "guidances": {
               "image_reference": [
                   {
                       "image": {
                           "id": "YOUR_UPLOADED_IMAGE_ID",
                           "type": "UPLOADED"
                       },
                       "strength": "MID"
                   }
               ]
           }
       },
       "public": false
   }'
```

#

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

| Parameter                  | Type      | Definition                                                                                                                                                     |
| :------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                         |
| guidances.image\_reference | `array`   | *Optional.* Array of up to 10 reference images. Each reference includes image.id, image.type (`GENERATED` or `UPLOADED`), and strength (`LOW`, `MID`, `HIGH`). |
| height                     | `integer` | *Optional.* Height input resolution. Supports `768` to `2048`. Defaults to `2048`.                                                                             |
| model                      | `string`  | *Required.* Model identifier. Set to `seedream-5.0-pro`.                                                                                                       |
| output\_format             | `string`  | *Optional.* Output image format. Supports `jpeg` or `png`. Defaults to `jpeg`.                                                                                 |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate.                                                                                  |
| prompt\_enhance            | `string`  | *Optional.* Controls prompt enhancement. Supports `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                  |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                       |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request. Supports `1` to `6`. Defaults to `1`.                                                            |
| seed                       | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets.                                                                                 |
| width                      | `integer` | *Optional.* Width input resolution. Supports `768` to `2048`. Defaults to `2048`.                                                                              |

<br />