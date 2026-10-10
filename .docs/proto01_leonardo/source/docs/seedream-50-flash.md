---
updatedAt: 2026-10-07T04:26:00.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedream 5.0 Flash

This guide shows how to generate images using the Seedream 5.0 Flash model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "bytedance/seedream-5.0-flash",
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
                       }
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

| Parameter                  | Type      | Definition                                                                                                                                                                                                 |
| :------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                                                                     |
| guidances.image\_reference | `array`   | *Optional.* Array of up to 10 reference images. Each reference includes `image.type` (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`) and the matching `image.id`, `image.url`, or `image.data`. |
| height                     | `integer` | *Optional.* Height input resolution. Supports `1024` to `3008`. Defaults to `2048`.                                                                                                                        |
| model                      | `string`  | *Required.* Model identifier. Set to `bytedance/seedream-5.0-flash`.                                                                                                                                       |
| output\_format             | `string`  | *Optional.* Output image format. Supports `jpeg` or `png`. Defaults to `jpeg`.                                                                                                                             |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate. Supports 1 to 9999 characters.                                                                                               |
| prompt\_enhance            | `string`  | *Optional.* Controls prompt enhancement. Supports `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                              |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`).                                                                                                   |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request. Supports `1` to `8`. Defaults to `1`.                                                                                                        |
| width                      | `integer` | *Optional.* Width input resolution. Supports `1024` to `3008`. Defaults to `2048`.                                                                                                                         |