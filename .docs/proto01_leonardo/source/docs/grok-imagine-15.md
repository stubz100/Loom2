---
updatedAt: 2026-06-23T05:25:38.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Grok Imagine 1.5

This guide shows how to generate videos using the Grok Imagine 1.5 model via the Leonardo.AI REST API.

# Grok Imagine 1.5

This guide shows how to generate videos using the **Grok Imagine 1.5** model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "grok-imagine-1.5",
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
        ]
      },
      "duration": 6,
      "width": 1280,
      "height": 720,
      "quantity": 1,
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

| Parameter              | Type      | Definition                                                                                                                                  |
| ---------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| duration               | `number`  | Length of the generated video in seconds. Set to `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, or `15`. Defaults to `6`. |
| guidances.start\_frame | `array`   | Required. Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, or `VARIATION`).       |
| height                 | `number`  | Sets the height of the output video in pixels. Set to `0`, `400`, `544`, `720`, `736`, `960`, or `1280`. Defaults to `720`.                 |
| model                  | `string`  | Specifies the model used for generation. Set to `grok-imagine-1.5`.                                                                         |
| motion\_has\_audio     | `boolean` | Whether the video generation will include audio. Defaults to `true`.                                                                        |
| prompt                 | `string`  | Text description of the video content to generate. Maximum of 5000 characters.                                                              |
| public                 | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                   |
| quantity               | `number`  | The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                             |
| width                  | `number`  | Sets the width of the output video in pixels. Set to `0`, `400`, `544`, `720`, `736`, `960`, or `1280`. Defaults to `1280`.                 |

## Dimensions

The API accepts `width` and `height` parameters in the following combinations:

| Aspect Ratio     | Pixel Values (Width x Height) |
| ---------------- | ----------------------------- |
| Auto             | 0x0                           |
| 1:1 (Square)     | 544x544                       |
| 1:1 (Square)     | 960x960                       |
| 16:9 (Landscape) | 1280x720                      |
| 9:16 (Portrait)  | 720x1280                      |
| 9:16 (Portrait)  | 400x736                       |
| 16:9 (Landscape) | 736x400                       |

<br />