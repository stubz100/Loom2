---
updatedAt: 2026-07-04T10:23:44.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Happy Horse 1.1

This guide shows how to generate videos using the Happy Horse 1.1 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "happy-horse-1.1",
    "public": false,
    "parameters": {
      "prompt": "YOUR_PROMPT",
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
      "quantity": 1,
      "prompt_enhance": "OFF",
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

| Parameter                  | Type      | Definition                                                                                                                                                                                                                                                     |
| :------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                   | `number`  | Length of the generated video in seconds. Set to any integer from `3` to `15`. Defaults to `5`.                                                                                                                                                                |
| guidances.image\_reference | `array`   | Maximum 9 items. References images to guide your video generation. Each item includes image.id, image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`), a required strength (`LOW`, `MID`, `HIGH`; defaults to `MID`), and an optional order. |
| guidances.start\_frame     | `array`   | Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, `VARIATION`).                                                                                                                                       |
| height                     | `number`  | Sets the height of the output video in pixels. Defaults to `1080`.                                                                                                                                                                                             |
| model                      | `string`  | Specifies the model used for generation. Set to `happy-horse-1.1`.                                                                                                                                                                                             |
| motion\_has\_audio         | `boolean` | Whether the generated video includes audio. Defaults to `true`.                                                                                                                                                                                                |
| prompt                     | `string`  | Required. Text description of the video content to generate. Maximum of 2500 characters.                                                                                                                                                                       |
| prompt\_enhance            | `string`  | Enables or disables prompt enhancement. Valid values are `AUTO`, `ON` and `OFF`. Defaults to `AUTO`.                                                                                                                                                           |
| public                     | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                                                                      |
| quantity                   | `number`  | Required. The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                                                                                                      |
| seed                       | `number`  | The seed value for generation.                                                                                                                                                                                                                                 |
| width                      | `number`  | Sets the width of the output video in pixels. Defaults to `1920`.                                                                                                                                                                                              |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 720p       | 16:9 (Landscape) | 1280x720                      |
|            | 4:3              | 1108x832                      |
|            | 1:1 (Square)     | 960x960                       |
|            | 3:4              | 832x1108                      |
|            | 9:16 (Portrait)  | 720x1280                      |
| 1080p      | 16:9 (Landscape) | 1920x1080                     |
|            | 4:3              | 1662x1248                     |
|            | 1:1 (Square)     | 1440x1440                     |
|            | 3:4              | 1248x1662                     |
|            | 9:16 (Portrait)  | 1080x1920                     |

<br />