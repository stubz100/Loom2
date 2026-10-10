---
updatedAt: 2026-07-15T04:28:58.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Wan 2.6

This guide shows how to generate videos using the Wan 2.6 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "wan-2.6",
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
        ]
      },
      "duration": 5,
      "negative_prompt": "",
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

| Parameter                        | Type      | Definition                                                                                                                                                                 |
| :------------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `number`  | Duration of the video in seconds. Set to `5`, `10`, or `15`. Defaults to `5`.                                                                                              |
| guidances.audio\_reference       | `array`   | Maximum 1 item. Each item includes audio.id and audio.type (`UPLOADED`). Specifies an audio reference for guidance.                                                        |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, or `VARIATION`).                                                |
| guidances.video\_reference\_base | `array`   | Maximum 3 items. Each item includes video.id and video.type (`UPLOADED` or `GENERATED`). Base video to be edited.                                                          |
| height                           | `number`  | Sets the height of the output video in pixels. See Dimensions for valid width and height combinations.                                                                     |
| model                            | `string`  | Specifies the model used for generation. Set to `wan-2.6`.                                                                                                                 |
| negative\_prompt                 | `string`  | Text description of content to avoid in the generated video. Maximum of 500 characters. Defaults to `""`.                                                                  |
| prompt                           | `string`  | Text description of the video content to generate. Maximum of 1500 characters.                                                                                             |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                  |
| quantity                         | `number`  | The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                            |
| resolution                       | `string`  | Output resolution when using AUTO dimensions (`width: 0`, `height: 0`) for image-to-video. Valid values are `720p` and `1080p`. Determines cost tier. Defaults to `1080p`. |
| seed                             | `number`  | Random seed for reproducible generation. Set between `0` and `2147483647`.                                                                                                 |
| width                            | `number`  | Sets the width of the output video in pixels. See Dimensions for valid width and height combinations.                                                                      |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 720p       | 16:9 (Landscape) | 1280x720                      |
|            | 4:3              | 960x720                       |
|            | 1:1 (Square)     | 960x960                       |
|            | 3:4              | 720x960                       |
|            | 9:16 (Portrait)  | 720x1280                      |
| 1080p      | 16:9 (Landscape) | 1920x1080                     |
|            | 4:3              | 1440x1080                     |
|            | 1:1 (Square)     | 1440x1440                     |
|            | 3:4              | 1080x1440                     |
|            | 9:16 (Portrait)  | 1080x1920                     |
| Auto       |                  | 0x0                           |

Setting `width: 0` and `height: 0` (AUTO) lets the model infer dimensions; use the `resolution` parameter to control the output resolution tier.