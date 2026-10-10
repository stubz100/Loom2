---
updatedAt: 2026-09-02T14:04:44.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Gemini Omni 1.1 Flash

This guide shows how to generate videos using the Gemini Omni 1.1 Flash model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "google/gemini-omni-1.1-flash-preview",
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
      "quantity": 1,
      "motion_has_audio": true,
      "width": 1280,
      "height": 720
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

| Parameter                        | Type      | Definition                                                                                                                                                                                                                   |
| :------------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `number`  | Length of the generated video in seconds. Set to `3`, `4`, `5`, `6`, `7`, `8`, `9`, or `10`. Defaults to `5`.                                                                                                                |
| guidances.end\_frame             | `array`   | Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`). Sets the final frame of the generated video.                                                          |
| guidances.image\_reference       | `array`   | Maximum 10 items. References images to guide your video generation. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`). An optional order sets the ordering of guidances. |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`). Sets the first frame of the generated video.                                                          |
| guidances.video\_reference\_base | `array`   | Maximum 3 items. Base video to be edited. Each item includes video.id, video.type (`UPLOADED` or `GENERATED`), and video.duration, which must not exceed `10` seconds.                                                       |
| height                           | `number`  | Sets the height of the output video in pixels.                                                                                                                                                                               |
| model                            | `string`  | Specifies the model used for generation. Set to `google/gemini-omni-1.1-flash-preview`.                                                                                                                                      |
| motion\_has\_audio               | `boolean` | Controls whether the video generation includes audio. Defaults to `true`.                                                                                                                                                    |
| prompt                           | `string`  | Text description of the video content to generate. Maximum of 2500 characters.                                                                                                                                               |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                                    |
| quantity                         | `number`  | The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                                                                              |
| width                            | `number`  | Sets the width of the output video in pixels.                                                                                                                                                                                |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 360p       | 16:9 (Landscape) | 640x360                       |
|            | 9:16 (Portrait)  | 360x640                       |
| 720p       | 16:9 (Landscape) | 1280x720                      |
|            | 9:16 (Portrait)  | 720x1280                      |
| 1080p      | 16:9 (Landscape) | 1920x1080                     |
|            | 9:16 (Portrait)  | 1080x1920                     |
| 4K         | 16:9 (Landscape) | 3840x2160                     |
|            | 9:16 (Portrait)  | 2160x3840                     |

`width` and `height` must be set together using one of the combinations above, or omitted together.