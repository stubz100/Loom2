---
updatedAt: 2026-07-10T04:11:46.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Wan 2.7

This guide shows how to generate videos using the Wan 2.7 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "wan-2.7",
    "public": false,
    "parameters": {
      "prompt": "The koala plays with the cat",
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
      "duration": 5,
      "width": 1920,
      "height": 1080
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

| Parameter                        | Type      | Definition                                                                                                                                                                                                                                                   |
| :------------------------------- | :-------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `number`  | Length of the generated video in seconds. Set to `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, or `10`. Defaults to `5`.                                                                                                                                           |
| guidances.end\_frame             | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`).                                                                                                                                                                      |
| guidances.image\_reference       | `array`   | Reference images to guide the video generation. Each item includes image.id, image.type (`GENERATED` or `UPLOADED`), and strength (`LOW`, `MID`, or `HIGH`; defaults to `MID`).                                                                              |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`).                                                                                                                                                                      |
| guidances.video\_reference\_base | `array`   | Maximum 1 item. Base video to be edited. Each item includes a `video` object with `id` and `type` (`UPLOADED` or `GENERATED`), and an optional item-level `type` (`BASE` or `FEATURE`): `BASE` routes to edit-video, `FEATURE` routes to reference-to-video. |
| height                           | `number`  | Sets the height of the output video in pixels.                                                                                                                                                                                                               |
| model                            | `string`  | Specifies the model used for generation. Set to `wan-2.7`.                                                                                                                                                                                                   |
| prompt                           | `string`  | Text description of the video content to generate. Maximum of 2500 characters.                                                                                                                                                                               |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                                                                    |
| quantity                         | `number`  | Number of outputs to generate. Defaults to `1` (maximum `1`).                                                                                                                                                                                                |
| resolution                       | `string`  | Output resolution for edit mode. Set to `720p` or `1080p`. Defaults to `1080p`.                                                                                                                                                                              |
| width                            | `number`  | Sets the width of the output video in pixels.                                                                                                                                                                                                                |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 720p       | 16:9 (Landscape) | 1280x720                      |
|            | 1:1 (Square)     | 960x960                       |
|            | 9:16 (Portrait)  | 720x1280                      |
| 1080p      | 16:9 (Landscape) | 1920x1080                     |
|            | 1:1 (Square)     | 1440x1440                     |
|            | 9:16 (Portrait)  | 1080x1920                     |
| Auto       | —                | 0x0                           |

<br />