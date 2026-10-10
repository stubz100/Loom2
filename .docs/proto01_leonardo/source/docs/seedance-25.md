---
updatedAt: 2026-08-18T05:07:51.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedance 2.5

This guide shows how to generate videos using the Seedance 2.5 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "model": "bytedance/seedance-2.5",
  "public": false,
  "parameters": {
    "prompt": "A koala and a cat playing together in a sunlit meadow",
    "quantity": 1,
    "width": 1280,
    "height": 720,
    "duration": 8,
    "motion_has_audio": true
  }
}
'
```

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

| Parameter                        | Type      | Definition                                                                                                                                                                                                       |
| :------------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `integer` | *Optional.* Duration of the video in seconds. Accepts `4` through `30` in whole-second increments. Defaults to `8`.                                                                                              |
| guidances                        | `object`  | *Optional.* Object defining guidance inputs (e.g. reference images, audio, base video, start/end frames) that influence the result.                                                                              |
| guidances.audio\_reference       | `array`   | *Optional.* Specifies a list of audio references for guidance. Maximum 10 items. Each item includes audio.id and audio.type (`UPLOADED`, `GENERATED`), and optionally audio.duration.                            |
| guidances.end\_frame             | `array`   | *Optional.* Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`).      |
| guidances.image\_reference       | `array`   | *Optional.* References images to guide your video generation. Maximum 30 items. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`), and optionally order.   |
| guidances.start\_frame           | `array`   | *Optional.* Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`).      |
| guidances.video\_reference\_base | `array`   | *Optional.* Base video to be edited. Maximum 10 items. Each item includes video.id and video.type (`UPLOADED`, `GENERATED`), and optionally video.width, video.height, video.duration, video.motion\_has\_audio. |
| height                           | `integer` | *Optional.* Height of the output in pixels. Defaults to `720`.                                                                                                                                                   |
| model                            | `string`  | *Required.* Specifies the model used for generation. Set to `bytedance/seedance-2.5`.                                                                                                                            |
| motion\_has\_audio               | `boolean` | *Optional.* Whether the video generation will include audio. Defaults to `True`.                                                                                                                                 |
| prompt                           | `string`  | *Required.* The prompt to use for the generation. Maximum 5000 characters.                                                                                                                                       |
| public                           | `boolean` | *Optional.* Controls whether the generation is public (`true`) or private (`false`).                                                                                                                             |
| quantity                         | `integer` | *Required.* The number of outputs to generate. Defaults to `1`. Range 1-1.                                                                                                                                       |
| seed                             | `number`  | *Optional.* The seed value for generation. Defaults to `-1`. Range -1 to 4294967295.                                                                                                                             |
| width                            | `integer` | *Optional.* Width of the output in pixels. Defaults to `1280`.                                                                                                                                                   |

## Dimensions

The API accepts integer `width` and `height` values in pixels. Defaults to `1280` x `720`.