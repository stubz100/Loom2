---
updatedAt: 2026-08-05T08:50:21.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# P-Image-Ideogram

This guide shows how to generate images using P-Image-Ideogram model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "ideogram/p-image-ideogram",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "A vintage travel poster of Mount Fuji at sunrise, bold art deco typography",
           "quality": "MEDIUM",
           "quantity": 4,
           "prompt_enhance": "AUTO"
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

### Headers

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter       | Type      | Definition                                                                                                                                                                                                                                                                        |
| :-------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| height          | `integer` | *Optional.* Height input resolution. Defaults to `1024`. Accepts one of: `512`, `640`, `720`, `800`, `832`, `864`, `896`, `1024`, `1120`, `1152`, `1248`, `1280`, `1440`, `1536`, `1600`, `1664`, `1728`, `1792`, `2048`, `2240`, `2304`, `2496`, `2560`, `2880`, `3072`, `3456`. |
| model           | `string`  | *Required.* Model identifier. Set to `ideogram/p-image-ideogram`.                                                                                                                                                                                                                 |
| prompt          | `string`  | *Required.* Text prompt describing what image you want the model to generate. Accepts `1` to `10000` characters.                                                                                                                                                                  |
| prompt\_enhance | `string`  | *Optional.* Controls prompt enhancement. One of `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                                                                                                       |
| public          | `boolean` | *Optional.* Determines whether the generated images show in the community feed (`true`) or stay private (`false`).                                                                                                                                                                |
| quality         | `string`  | *Optional.* Output quality tier. One of `VERY_LOW`, `LOW`, `MEDIUM`, or `HIGH`. Defaults to `MEDIUM`. Use `quality` instead of `mode` for third-party models.                                                                                                                     |
| quantity        | `integer` | *Optional.* Number of images to generate in a single request. Accepts `1` to `8`. Defaults to `4`.                                                                                                                                                                                |
| width           | `integer` | *Optional.* Width input resolution. Defaults to `1024`. Accepts one of: `512`, `640`, `720`, `800`, `832`, `864`, `896`, `1024`, `1120`, `1152`, `1248`, `1280`, `1440`, `1536`, `1600`, `1664`, `1728`, `1792`, `2048`, `2240`, `2304`, `2496`, `2560`, `2880`, `3072`, `3456`.  |