---
updatedAt: 2026-07-10T13:43:52.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Lucid Origin

This guide shows how to generate images using Lucid Origin model via the Leonardo.AI REST API.

**Note:** Lucid Origin is available through the MCP Server (Multi-Cloud Proxy) workflow as well — see [Connect to Leonardo.AI with the MCP Server](https://docs.leonardo.ai/docs/connect-to-leonardoai-mcp).

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "lucid-origin",
       "parameters": {
           "mode": "FAST",
           "width": 1200,
           "height": 1200,
           "prompt": "a portrait-style photograph featuring a fox with soft, fluffy orange fur against a smooth navy blue background",
           "quantity": 4,
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ]
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

| Parameter         | Type      | Definition                                                                                                                                                                                                                                           |
| ----------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| guidances         | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                                                                                                               |
| guidances.content | `array`   | *Optional.* References the form and content from an input image to guide the generation (limited to 1). Each reference includes `image.id`, `image.type` (`UPLOADED` or `GENERATED`), and `strength` (`LOW`, `MID`, `HIGH`). Defaults to `MID`.      |
| guidances.style   | `array`   | *Optional.* References the style from an input image to guide the generation (limited to 1). Each reference includes `image.id`, `image.type` (`UPLOADED` or `GENERATED`), and `strength` (`LOW`, `MID`, `HIGH`, `ULTRA`, `MAX`). Defaults to `MID`. |
| height            | `integer` | *Optional.* Height of the image to generate in pixels. Supports `16` to `3616` in multiples of `8`. Defaults to `1200`.                                                                                                                              |
| mode              | `string`  | *Optional.* Generation mode. Accepts `FAST` or `ULTRA`. Use this instead of `quality` for all proprietary models. Defaults to `FAST`.                                                                                                                |
| model             | `string`  | *Required.* Model identifier. Set to `lucid-origin`.                                                                                                                                                                                                 |
| prompt            | `string`  | *Required.* Text prompt describing what image you want the model to generate. Maximum `2000` characters.                                                                                                                                             |
| prompt\_enhance   | `string`  | *Optional.* Controls prompt enhancement. Accepts `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                                                                         |
| public            | `boolean` | *Optional.* Boolean flag that determines whether the generated images show in the community feed (`true`) or remain private (`false`).                                                                                                               |
| quantity          | `integer` | *Optional.* Number of images to generate in a single request. Supports `1` to `8`. Defaults to `4`.                                                                                                                                                  |
| seed              | `integer` | *Optional.* Apply a fixed seed (`0` to `2147483647`) to maintain consistency across generation sets.                                                                                                                                                 |
| style\_ids        | `array`   | *Optional.* Array of style UUIDs used to apply a preset style to the output (limited to 1 style). Defaults to `["111dc692-d470-4eec-b791-3475abac4c46"]` (Dynamic). Refer to the table below for a list of UUIDs.                                    |
| width             | `integer` | *Optional.* Width of the image to generate in pixels. Supports `16` to `3840` in multiples of `8`. Defaults to `1200`.                                                                                                                               |

### List of Style IDs

| Preset Style | UUID                                   |
| ------------ | -------------------------------------- |
| Cinematic    | `a5632c7c-ddbb-4e2f-ba34-8456ab3ac436` |
| Creative     | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic      | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion      | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| None         | `556c1ee5-ec38-42e8-955a-1e82dad0ffa1` |
| Portrait     | `ab5a4220-7c42-41e5-a578-eddb9fed3d75` |
| Stock Photo  | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Vibrant      | `dee282d3-891f-4f73-ba02-7f8131e5541b` |

<br />