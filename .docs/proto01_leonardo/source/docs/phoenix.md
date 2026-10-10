---
updatedAt: 2026-07-10T14:05:31.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Phoenix

This guide shows how to generate images using Phoenix models via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "phoenix-v1.0",
       "parameters": {
           "mode": "FAST",
           "contrast": "MEDIUM",
           "width": 1472,
           "height": 832,
           "prompt": "an orange cat standing on a blue basketball with the text PAWS",
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

## Headers

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                  | Type      | Definition                                                                                                                                                                                                                                           |
| :------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| contrast                   | `string`  | *Optional.* The contrast the image should have. Accepts `LOW`, `MEDIUM`, or `HIGH`. Defaults to `MEDIUM`.                                                                                                                                            |
| guidances                  | `object`  | *Optional.* Object defining image guidance inputs that influence the generated result.                                                                                                                                                               |
| guidances.character        | `array`   | *Optional.* References a character from an input image to guide the generation (limited to 1). Each reference includes `image.id`, `image.type` (`UPLOADED` or `GENERATED`), and `strength` (`LOW`, `MID`, `HIGH`). Defaults to `MID`.               |
| guidances.content          | `array`   | *Optional.* References the form and content from an input image to guide the generation (limited to 1). Each reference includes `image.id`, `image.type` (`UPLOADED` or `GENERATED`), and `strength` (`LOW`, `MID`, `HIGH`). Defaults to `MID`.      |
| guidances.image\_to\_image | `array`   | *Optional.* Uses an input image as the starting point for the generation (limited to 1). Each reference includes `image.id`, `image.type` (`UPLOADED` or `GENERATED`), and `strength` (`LOW`, `MID`, `HIGH`). Defaults to `MID`.                     |
| guidances.style            | `array`   | *Optional.* References the style from an input image to guide the generation (limited to 4). Each reference includes `image.id`, `image.type` (`UPLOADED` or `GENERATED`), and `strength` (`LOW`, `MID`, `HIGH`, `ULTRA`, `MAX`). Defaults to `MID`. |
| height                     | `integer` | *Optional.* Height of the image to generate in pixels. Supports `32` to `2048` in multiples of `8`. Defaults to `1024`.                                                                                                                              |
| mode                       | `string`  | *Optional.* Generation mode. Accepts `FAST`, `QUALITY`, or `ULTRA`. Use this instead of `quality` for all proprietary models. Defaults to `FAST`.                                                                                                    |
| model                      | `string`  | *Required.* Model identifier. Set to `phoenix-v1.0` or `phoenix-v0.9`. Refer to the table below for a list of models.                                                                                                                                |
| negative\_prompt           | `string`  | *Optional.* The negative prompt to use for the generation.                                                                                                                                                                                           |
| prompt                     | `string`  | *Required.* Text prompt describing what image you want the model to generate. Maximum `2000` characters.                                                                                                                                             |
| prompt\_enhance            | `string`  | *Optional.* Controls prompt enhancement. Accepts `AUTO`, `ON`, or `OFF`. Defaults to `AUTO`.                                                                                                                                                         |
| public                     | `boolean` | *Optional.* Boolean flag that determines whether the generated images show in the community feed (`true`) or remain private (`false`).                                                                                                               |
| quantity                   | `integer` | *Optional.* Number of images to generate in a single request. Supports `1` to `8`. Defaults to `4`.                                                                                                                                                  |
| seed                       | `integer` | *Optional.* Apply a fixed seed (minimum `0`) to maintain consistency across generation sets.                                                                                                                                                         |
| style\_ids                 | `array`   | *Optional.* Array of style UUIDs used to apply a preset style to the output (limited to 1 style). Defaults to `["111dc692-d470-4eec-b791-3475abac4c46"]` (Dynamic). Refer to the table below for a list of UUIDs.                                    |
| tiling                     | `boolean` | *Optional.* When `true`, enables tiling.                                                                                                                                                                                                             |
| width                      | `integer` | *Optional.* Width of the image to generate in pixels. Supports `32` to `2048` in multiples of `8`. Defaults to `1024`.                                                                                                                               |

## List of Models

| Preset      | Model       | model          |
| :---------- | :---------- | :------------- |
| Phoenix 1.0 | Phoenix 1.0 | `phoenix-v1.0` |
| Phoenix 0.9 | Phoenix 0.9 | `phoenix-v0.9` |

## List of Style IDs

Both Phoenix 1.0 and Phoenix 0.9 accept the same set of style UUIDs.

| Preset Style           | UUID                                   |
| :--------------------- | :------------------------------------- |
| 3D Render              | `debdf72a-91a4-467b-bf61-cc02bdeb69c6` |
| Bokeh                  | `9fdc5e8c-4d13-49b4-9ce6-5a74cbb19177` |
| Cinematic              | `a5632c7c-ddbb-4e2f-ba34-8456ab3ac436` |
| Cinematic Concept      | `33abbb99-03b9-4dd7-9761-ee98650b2c88` |
| Creative               | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic                | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion                | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| Graphic Design Pop Art | `2e74ec31-f3a4-4825-b08b-2894f6d13941` |
| Graphic Design Vector  | `1fbb6a68-9319-44d2-8d56-2957ca0ece6a` |
| Illustration           | `645e4195-f63d-4715-a3f2-3fb1e6eb8c70` |
| Macro                  | `30c1d34f-e3a9-479a-b56f-c018bbc9c02a` |
| Minimalist             | `cadc8cd6-7838-4c99-b645-df76be8ba8d8` |
| Moody                  | `621e1c9a-6319-4bee-a12d-ae40659162fa` |
| None                   | `556c1ee5-ec38-42e8-955a-1e82dad0ffa1` |
| Portrait               | `ab5a4220-7c42-41e5-a578-eddb9fed3d75` |
| Pro B\&W photography   | `22a9a7d2-2166-4d86-80ff-22e2643adbcf` |
| Pro color photography  | `7c3f932b-a572-47cb-9b9b-f20211e63b5b` |
| Pro film photography   | `581ba6d6-5aac-4492-bebe-54c424a0d46e` |
| Ray Traced             | `b504f83c-3326-4947-82e1-7fe9e839ec0f` |
| Sketch (B\&W)          | `be8c6b58-739c-4d44-b9c1-b032ed308b61` |
| Sketch (Color)         | `093accc3-7633-4ffd-82da-d34000dfc0d6` |
| Stock Photo            | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Vibrant                | `dee282d3-891f-4f73-ba02-7f8131e5541b` |

# Image Guidance

## Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "phoenix-v1.0",
       "parameters": {
           "prompt": "Intricately swirling nebulas dance across a vividly colored galactic map",
           "width": 1024,
           "height": 1024,
           "guidances": {
               "content": [
                   {
                       "image": {
                           "id": "06c4d15c-0d32-42b3-bec2-4e1d685d229f",
                           "type": "UPLOADED"
                       },
                       "strength": "HIGH"
                   }
               ]
           }
       },
       "public": false
   }'
```

Image guidance is configured through the `guidances` object. Phoenix models support Style Reference (`guidances.style`, up to 4 references), Content Reference (`guidances.content`, limited to 1), Character Reference (`guidances.character`, limited to 1), and Image to Image (`guidances.image_to_image`, limited to 1). See the Body Parameters table above for the fields each reference accepts.

<br />