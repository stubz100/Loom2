---
updatedAt: 2026-07-04T08:42:15.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Veo 3.1

This guide shows how to generate videos using the Veo 3.1, Veo 3.1 Fast, and Veo 3.1 Lite models via the Leonardo.AI REST API.

<br />

These three models belong to the same Veo 3.1 family and share an identical request structure. You can switch between `veo-3.1-generate-001`, `veo-3.1-fast-generate-001`, and `veo-3.1-lite` by changing only the `model` field. The differences are: Veo 3.1 and Veo 3.1 Fast support resolutions up to 4K (2160p), while Veo 3.1 Lite supports up to 1080p; and the `guidances.image_reference` parameter is available only on `veo-3.1-generate-001`.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "veo-3.1-generate-001",
    "public": false,
    "parameters": {
      "prompt": "<YOUR_PROMPT>",
      "guidances": {
        "start_frame": [
          {
            "image": {
              "id": "<YOUR_START_IMAGE_ID>",
              "type": "UPLOADED"
            }
          }
        ],
        "end_frame": [
          {
            "image": {
              "id": "<YOUR_END_IMAGE_ID>",
              "type": "UPLOADED"
            }
          }
        ]
      },
      "duration": 8,
      "motion_has_audio": true,
      "quantity": 1,
      "width": 1280,
      "height": 720
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

| Parameter                  | Type      | Definition                                                                                                                                                                                                   |
| :------------------------- | :-------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                   | `integer` | Length of the generated video in seconds. Set to `4`, `6`, or `8`. Defaults to `8`.                                                                                                                          |
| guidances.end\_frame       | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when `start_frame` is provided.                                                                       |
| guidances.image\_reference | `array`   | Reference images to guide your video generation. Maximum 3 items. Each item includes image.id, image.type, and strength (`LOW`, `MID`, `HIGH`; defaults to `MID`). Available only on `veo-3.1-generate-001`. |
| guidances.start\_frame     | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`).                                                                                                                      |
| height                     | `integer` | Sets the height of the output video in pixels. See the Dimensions table for accepted values.                                                                                                                 |
| model                      | `string`  | Specifies the model used for generation. Set to `veo-3.1-generate-001`, `veo-3.1-fast-generate-001`, or `veo-3.1-lite`. These three models are interchangeable and accept the same request structure.        |
| motion\_has\_audio         | `boolean` | Whether the video generation will include audio. Valid values are `true` and `false`. Defaults to `true`.                                                                                                    |
| negative\_prompt           | `string`  | The negative prompt to use for the generation. Maximum of 1000 characters.                                                                                                                                   |
| prompt                     | `string`  | Text description of the video content to generate. Maximum of 9999 characters.                                                                                                                               |
| public                     | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                    |
| quantity                   | `integer` | The number of outputs to generate. Must be `1`. Defaults to `1`.                                                                                                                                             |
| seed                       | `number`  | The seed value for generation. Accepts a value from `0` to `4294967295`.                                                                                                                                     |
| width                      | `integer` | Sets the width of the output video in pixels. See the Dimensions table for accepted values.                                                                                                                  |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution                                 | Aspect Ratio     | Pixel Values (Width x Height) |
| :----------------------------------------- | :--------------- | :---------------------------- |
| 720p                                       | 16:9 (Landscape) | 1280x720                      |
|                                            | 9:16 (Portrait)  | 720x1280                      |
| 1080p                                      | 16:9 (Landscape) | 1920x1080                     |
|                                            | 9:16 (Portrait)  | 1080x1920                     |
| 2160p / 4K (not supported on Veo 3.1 Lite) | 16:9 (Landscape) | 3840x2160                     |
|                                            | 9:16 (Portrait)  | 2160x3840                     |

<br />