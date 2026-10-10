---
updatedAt: 2026-06-23T05:25:25.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Kling 3.0 Turbo

This guide shows how to generate videos using the Kling 3.0 Turbo model via the Leonardo.AI REST API.

# Kling 3.0 Turbo

This guide shows how to generate videos using the **Kling 3.0 Turbo** model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "kling-3.0-turbo",
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
      "motion_has_audio": true,
      "width": 1920,
      "height": 1080
    }
}
'
```

# Recipe

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

| Parameter              | Type      | Definition                                                                                                                                                                                                                                                      |
| :--------------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration               | `integer` | Duration of the video in seconds. Set to `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, or `15`. Defaults to `5`.                                                                                                                             |
| guidances.start\_frame | `array`   | Maximum 1 item. Each item includes image.id and image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, or `VARIATION`). Use a reference image to seed the video.                                                                                            |
| height                 | `integer` | Sets the height of the output video in pixels. See the Dimensions table for valid values.                                                                                                                                                                       |
| mode                   | `string`  | Deprecated. Width and height are the canonical inputs for this model; this field is retained for backwards compatibility. `RESOLUTION_720` routes to the standard (720p) tier, `RESOLUTION_1080` routes to the pro (1080p) tier. Defaults to `RESOLUTION_1080`. |
| model                  | `string`  | Specifies the model used for generation. Set to `kling-3.0-turbo`.                                                                                                                                                                                              |
| motion\_has\_audio     | `boolean` | Whether the video generation will include audio. Defaults to `true`.                                                                                                                                                                                            |
| prompt                 | `string`  | Text description of the video content to generate. Maximum of 2500 characters.                                                                                                                                                                                  |
| public                 | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                                                                       |
| quantity               | `integer` | The number of outputs to generate. Minimum `1`, maximum `1`. Defaults to `1`.                                                                                                                                                                                   |
| width                  | `integer` | Sets the width of the output video in pixels. See the Dimensions table for valid values.                                                                                                                                                                        |

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
| Auto       | Model-selected   | 0x0                           |

<br />