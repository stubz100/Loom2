---
updatedAt: 2026-06-30T04:15:03.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedance 2.0 Mini

This guide shows how to generate videos using the Seedance 2.0 Mini model via the Leonardo.AI REST API.

This guide shows how to generate videos using the **Seedance 2.0 Mini** model via the Leonardo.AI REST API.

<br />

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "seedance-2.0-mini",
    "public": false,
    "parameters": {
      "prompt": "A koala surfs a wave at sunset, cinematic",
      "quantity": 1,
      "duration": 8,
      "width": 1280,
      "height": 720,
      "motion_has_audio": true,
      "guidances": {
        "start_frame": [
          {
            "image": {
              "id": "<YOUR_START_IMAGE_ID>",
              "type": "UPLOADED"
            }
          }
        ]
      }
    }
}
'
```

<br />

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

| Parameter                        | Type      | Definition                                                                                                                                                              |
| :------------------------------- | :-------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `number`  | Length of the generated video in seconds. Valid values are `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`. Defaults to `8`.                           |
| guidances.audio\_reference       | `array`   | Maximum 1 item. Each item includes audio.id and audio.type (`UPLOADED`). Supplies an audio reference for guidance.                                                      |
| guidances.end\_frame             | `array`   | Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`).                                                                                   |
| guidances.image\_reference       | `array`   | Maximum 4 items. Each item includes image.id, image.type, optional order, and strength (`LOW`, `MID`, `HIGH`; defaults to `MID`). References images to guide the video. |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`).                                                                                   |
| guidances.video\_reference\_base | `array`   | Maximum 3 items. Each item includes video.id and video.type (`UPLOADED`, `GENERATED`). Supplies a base video to be edited.                                              |
| height                           | `number`  | Sets the height of the output video in pixels. Defaults to `720`.                                                                                                       |
| model                            | `string`  | Specifies the model used for generation. Must be `seedance-2.0-mini`. Required.                                                                                         |
| motion\_has\_audio               | `boolean` | Controls whether the generated video includes audio. Defaults to `true`.                                                                                                |
| prompt                           | `string`  | Text description of the video content to generate. Between 1 and 5000 characters. Required.                                                                             |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                               |
| quantity                         | `number`  | The number of outputs to generate. Minimum `1`, maximum `1`. Defaults to `1`. Required.                                                                                 |
| seed                             | `number`  | The seed value for generation. Range `-1` to `4294967295`. Defaults to `-1`.                                                                                            |
| width                            | `number`  | Sets the width of the output video in pixels. Defaults to `1280`.                                                                                                       |

## Dimensions

The `width` and `height` parameters accept integer pixel values and default to `1280` x `720` (16:9). The OpenAPI schema does not enumerate a fixed set of allowed width/height combinations for this model, so refer to the in-product Seedance 2.0 Mini documentation for the supported resolutions and aspect ratios.