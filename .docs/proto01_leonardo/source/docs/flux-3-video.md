---
updatedAt: 2026-08-19T01:08:22.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# FLUX 3 Video

This guide shows how to generate videos using the FLUX 3 Video model via the Leonardo.AI REST API.  #

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "bfl/flux-3-video",
    "public": false,
    "parameters": {
      "prompt": "A koala drifting down a river on a surfboard at golden hour",
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
      "resolution": "1080p",
      "motion_has_audio": true,
      "width": 1920,
      "height": 1080
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

| Parameter                        | Type      | Definition                                                                                                                                                                                  |
| :------------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| duration                         | `number`  | Length of the generated video in seconds. Set to `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`, or `20`. Defaults to `8`.                             |
| guidances.end\_frame             | `array`   | Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, or `VARIATION`).                                                                 |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, or `VARIATION`).                                                                 |
| guidances.video\_reference\_base | `array`   | Base video to be edited. Maximum 1 item. Each item includes video.id and video.type (`UPLOADED` or `GENERATED`). Each item must be at most 15 seconds and under 50 MB.                      |
| height                           | `number`  | Sets the height of the output video in pixels.                                                                                                                                              |
| model                            | `string`  | Required. Specifies the model used for generation. Set to `bfl/flux-3-video`.                                                                                                               |
| motion\_has\_audio               | `boolean` | Controls whether the generated video includes audio. Defaults to `true`.                                                                                                                    |
| prompt                           | `string`  | Required. Text description of the video content to generate. Maximum of 5000 characters.                                                                                                    |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                   |
| quantity                         | `number`  | Number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                                                 |
| resolution                       | `string`  | Output resolution, used when `width` and `height` are not supplied. Valid values are `720p` and `1080p`. Explicit `width` and `height` take precedence over this value. Defaults to `720p`. |
| width                            | `number`  | Sets the width of the output video in pixels.                                                                                                                                               |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 720p       | 21:9             | 1470x630                      |
|            | 2:1              | 1360x680                      |
|            | 16:9 (Landscape) | 1280x720                      |
|            | 4:3              | 1112x834                      |
|            | 1:1 (Square)     | 960x960                       |
|            | 3:4              | 834x1112                      |
|            | 9:16 (Portrait)  | 720x1280                      |
| 1080p      | 21:9             | 2520x1080                     |
|            | 2:1              | 2160x1080                     |
|            | 16:9 (Landscape) | 1920x1080                     |
|            | 4:3              | 1440x1080                     |
|            | 1:1 (Square)     | 1440x1440                     |
|            | 3:4              | 1080x1440                     |
|            | 9:16 (Portrait)  | 1080x1920                     |
| Auto       | Matches input    | 0x0                           |