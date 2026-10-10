---
updatedAt: 2026-07-10T13:44:58.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Lucid Realism

This guide shows how to generate images using Lucid Realism models via the Leonardo.AI REST API.

**Note:** Lucid Origin and Lucid Realism are available through the MCP Server (Multi-Cloud Proxy) workflow as well — see [Connect to Leonardo.AI with the MCP Server](https://docs.leonardo.ai/docs/connect-to-leonardoai-mcp).

# Lucid Realism

This guide shows how to generate images using Lucid Realism model via the Leonardo.AI REST API.

# Sample Request

<br />

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "lucid-realism",
       "parameters": {
           "mode": "FAST",
           "width": 1024,
           "height": 1024,
           "prompt": "a photorealistic portrait of a woman in golden hour light, shallow depth of field, natural skin texture",
           "quantity": 4,
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ]
       },
       "public": false
   }'
```

# Recipe

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
| height            | `integer` | *Optional.* Height of the image to generate in pixels. Supports `16` to `2496` in multiples of `8`. Defaults to `1024`.                                                                                                                              |
| mode              | `string`  | *Optional.* Generation mode. Accepts `FAST` or `ULTRA`. Use this instead of `quality` for all proprietary models. Defaults to `FAST`.                                                                                                                |
| model             | `string`  | *Required.* Model identifier. Set to `lucid-realism`.                                                                                                                                                                                                |
| prompt            | `string`  | *Required.* Text prompt describing what image you want the model to generate. Maximum `9999` characters.                                                                                                                                             |
| prompt\_enhance   | `string`  | *Optional.* Controls prompt enhancement. Accepts `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                                                                         |
| public            | `boolean` | *Optional.* Boolean flag that determines whether the generated images show in the community feed (`true`) or remain private (`false`).                                                                                                               |
| quantity          | `integer` | *Optional.* Number of images to generate in a single request. Supports `1` to `8`. Defaults to `4`.                                                                                                                                                  |
| seed              | `integer` | *Optional.* Apply a fixed seed (`0` to `2147483647`) to maintain consistency across generation sets.                                                                                                                                                 |
| style\_ids        | `array`   | *Optional.* Array of style UUIDs used to apply a preset style to the output (limited to 1 style). Defaults to `["111dc692-d470-4eec-b791-3475abac4c46"]` (Dynamic). Refer to the table below for a list of UUIDs.                                    |
| width             | `integer` | *Optional.* Width of the image to generate in pixels. Supports `16` to `2496` in multiples of `8`. Defaults to `1024`.                                                                                                                               |

### List of Style IDs

| Preset Style       | UUID                                   |
| ------------------ | -------------------------------------- |
| Bokeh              | `9fdc5e8c-4d13-49b4-9ce6-5a74cbb19177` |
| Cinematic          | `a5632c7c-ddbb-4e2f-ba34-8456ab3ac436` |
| Cinematic Close-Up | `cc53f935-884c-40a0-b7eb-1f5c42821fb5` |
| Creative           | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic            | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion            | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| Film               | `85da2dcc-c373-464c-9a7a-5624359be859` |
| Food               | `d574325d-1278-4fe2-974b-768525f253c3` |
| HDR                | `97c20e5c-1af6-4d42-b227-54d03d8f0727` |
| Long Exposure      | `335e6010-a75c-45d9-afc5-032c65e9180e` |
| Macro              | `30c1d34f-e3a9-479a-b56f-c018bbc9c02a` |
| Minimalist         | `cadc8cd6-7838-4c99-b645-df76be8ba8d8` |
| Monochrome         | `a2f7ea66-959b-4bbe-b508-6133238b76b6` |
| Moody              | `621e1c9a-6319-4bee-a12d-ae40659162fa` |
| Neutral            | `0d914779-c822-430a-b976-30075033f1c4` |
| None               | `556c1ee5-ec38-42e8-955a-1e82dad0ffa1` |
| Portrait           | `ab5a4220-7c42-41e5-a578-eddb9fed3d75` |
| Retro              | `6105baa2-851b-446e-9db5-08a671a8c42f` |
| Stock Photo        | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Unprocessed        | `62736842-6e4b-4028-b79a-4f1a1606e893` |
| Vibrant            | `dee282d3-891f-4f73-ba02-7f8131e5541b` |

<br />