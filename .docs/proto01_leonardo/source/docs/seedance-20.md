---
updatedAt: 2026-07-09T02:07:29.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedance 2.0

This guide shows how to generate videos using the Seedance 2.0 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "model": "seedance-2.0",
  "public": false,
  "parameters": {
    "prompt": "A koala and a cat playing together in a sunlit meadow",
    "quantity": 1,
    "width": 1280,
    "height": 720,
    "mode": "RESOLUTION_720",
    "duration": 8,
    "motion_has_audio": true
  }
}
'
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

| Parameter                        | Type      | Definition                                                                                                                                                                                                               |
| :------------------------------- | :-------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `integer` | *Optional.* Duration of the video in seconds. Accepts `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`. Defaults to `8`.                                                                                 |
| guidances                        | `object`  | *Optional.* Object defining guidance inputs (e.g. reference images, start/end frames) that influence the result.                                                                                                         |
| guidances.audio\_reference       | `array`   | *Optional.* Maximum 1 item.                                                                                                                                                                                              |
| guidances.end\_frame             | `array`   | *Optional.* Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`).              |
| guidances.image\_reference       | `array`   | *Optional.* References images to guide your video generation. Maximum 4 items. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`), strength (`LOW`, `MID`, `HIGH`). |
| guidances.start\_frame           | `array`   | *Optional.* Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`).              |
| guidances.video\_reference\_base | `array`   | *Optional.* Maximum 3 items.                                                                                                                                                                                             |
| height                           | `integer` | *Optional.* Height of the output in pixels. Defaults to `720`.                                                                                                                                                           |
| mode                             | `string`  | *Optional.* Resolution mode for the generation. Accepts `RESOLUTION_480`, `RESOLUTION_720`, `RESOLUTION_1080`. Defaults to `RESOLUTION_720`.                                                                             |
| model                            | `string`  | *Required.* Specifies the model used for generation. Set to `seedance-2.0`.                                                                                                                                              |
| motion\_has\_audio               | `boolean` | *Optional.* Whether the video generation will include audio. Defaults to `True`.                                                                                                                                         |
| prompt                           | `string`  | *Required.* The prompt to use for the generation. Maximum 5000 characters.                                                                                                                                               |
| public                           | `boolean` | *Optional.* Controls whether the generation is public (`true`) or private (`false`).                                                                                                                                     |
| quantity                         | `integer` | *Required.* The number of outputs to generate. Defaults to `1`. Range 1-1.                                                                                                                                               |
| seed                             | `number`  | *Optional.* The seed value for generation. Defaults to `-1`.                                                                                                                                                             |
| width                            | `integer` | *Optional.* Width of the output in pixels. Defaults to `1280`.                                                                                                                                                           |

## Dimensions

The API accepts integer `width` and `height` values in pixels. Defaults to `1280` x `720`.

The `mode` parameter accepts: `RESOLUTION_480`, `RESOLUTION_720`, `RESOLUTION_1080`.