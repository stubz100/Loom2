---
updatedAt: 2026-10-07T04:15:30.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Ideogram 4.5

This guide shows how to generate images using the Ideogram 4.5 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "ideogram/ideogram-4.5",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "A retro-futuristic concert poster for a synthwave band, bold chrome lettering that reads NEON HORIZON, a glowing sunset grid landscape, palm silhouettes, high contrast magenta and teal palette",
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

## Headers

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                               | Type      | Definition                                                                                                                                                                                                                                                                          |
| :-------------------------------------- | :-------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| guidances.image\_reference              | `array`   | *Optional.* Reference images used to guide the image generation. Accepts up to `5` items.                                                                                                                                                                                           |
| guidances.image\_reference.image        | `object`  | *Required* (for each `image_reference` item). The reference image object.                                                                                                                                                                                                           |
| guidances.image\_reference.image.data   | `string`  | *Optional.* Base64-encoded image bytes. Required when `type` is `BASE64`.                                                                                                                                                                                                           |
| guidances.image\_reference.image.height | `integer` | *Optional.* Height of the reference image.                                                                                                                                                                                                                                          |
| guidances.image\_reference.image.id     | `string`  | *Optional.* UUID of the reference image. Use with `type` set to `UPLOADED`, `GENERATED`, or `VARIATION`.                                                                                                                                                                            |
| guidances.image\_reference.image.type   | `string`  | *Optional.* Source of the reference image. One of `UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`.                                                                                                                                                                         |
| guidances.image\_reference.image.url    | `string`  | *Optional.* Image URL or a base64 data URL. Required when `type` is `URL`.                                                                                                                                                                                                          |
| guidances.image\_reference.image.width  | `integer` | *Optional.* Width of the reference image.                                                                                                                                                                                                                                           |
| guidances.image\_reference.order        | `integer` | *Optional.* Position of this reference in the list of guidances. Minimum `0`.                                                                                                                                                                                                       |
| height                                  | `integer` | *Optional.* Height input resolution. Defaults to `1024`. Accepts one of: `720`, `800`, `832`, `864`, `896`, `1024`, `1120`, `1152`, `1248`, `1280`, `1296`, `1440`, `1600`, `1664`, `1728`, `1792`, `2048`, `2240`, `2304`, `2496`, `2560`, `2880`, `2944`, `3072`, `3168`, `3328`. |
| model                                   | `string`  | *Required.* Model identifier. Set to `ideogram/ideogram-4.5`.                                                                                                                                                                                                                       |
| prompt                                  | `string`  | *Required.* Text prompt describing what image you want the model to generate. Accepts `1` to `10000` characters.                                                                                                                                                                    |
| prompt\_enhance                         | `string`  | *Optional.* Controls prompt enhancement. One of `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                                                                                                         |
| public                                  | `boolean` | *Optional.* Determines whether the generated images show in the community feed (`true`) or stay private (`false`).                                                                                                                                                                  |
| quality                                 | `string`  | *Optional.* Output quality tier. One of `VERY_LOW`, `LOW`, `MEDIUM`, or `HIGH`. Defaults to `MEDIUM`. Use `quality` instead of `mode` for third-party models.                                                                                                                       |
| quantity                                | `integer` | *Optional.* Number of images to generate in a single request. Accepts `1` to `8`. Defaults to `4`.                                                                                                                                                                                  |
| seed                                    | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets. Accepts `0` to `2147483647`.                                                                                                                                                                         |
| width                                   | `integer` | *Optional.* Width input resolution. Defaults to `1024`. Accepts one of: `720`, `800`, `832`, `864`, `896`, `1024`, `1120`, `1152`, `1248`, `1280`, `1296`, `1440`, `1600`, `1664`, `1728`, `1792`, `2048`, `2240`, `2304`, `2496`, `2560`, `2880`, `2944`, `3072`, `3168`, `3328`.  |