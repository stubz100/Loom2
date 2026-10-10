---
updatedAt: 2026-07-15T07:43:50.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Krea 2 Turbo

This guide shows how to generate images using the Krea 2 Turbo model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "krea-2-turbo",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "Koala with purple wizard hat on a skateboard",
           "quantity": 2
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

| Parameter       | Type      | Definition                                                                                                              |
| :-------------- | :-------- | :---------------------------------------------------------------------------------------------------------------------- |
| height          | `integer` | *Optional.* Height of the image to generate in pixels. Supports `16` to `4096` in multiples of `8`. Defaults to `1024`. |
| model           | `string`  | *Required.* Model identifier. Set to `krea-2-turbo`.                                                                    |
| prompt          | `string`  | *Required.* Text prompt describing what image you want the model to generate. Supports up to `9999` characters.         |
| prompt\_enhance | `string`  | *Optional.* Controls prompt enhancement. Supports `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                           |
| public          | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                |
| quantity        | `integer` | *Optional.* Number of images to generate in a single request. Supports `1` to `8`. Defaults to `4`.                     |
| width           | `integer` | *Optional.* Width of the image to generate in pixels. Supports `16` to `4096` in multiples of `8`. Defaults to `1024`.  |

<br />