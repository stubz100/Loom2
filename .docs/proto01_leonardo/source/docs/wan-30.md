---
updatedAt: 2026-08-24T07:13:57.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Wan 3.0

This guide shows how to generate videos using the **Wan 3.0** model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "alibaba/wan-3.0",
    "public": false,
    "parameters": {
      "prompt": "The koala plays with the cat in a sunlit eucalyptus grove",
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

| Parameter                        | Type      | Definition                                                                                                                                                                                    |
| :------------------------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `number`  | Length of the generated video in seconds. Any whole number from `2` to `30`. Defaults to `5`.                                                                                                 |
| guidances.audio\_reference       | `array`   | Audio references used to guide the generation. Maximum 5 items. Each item includes audio.id and audio.type (`GENERATED` or `UPLOADED`), and optionally audio.url and audio.duration.          |
| guidances.end\_frame             | `array`   | Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`). Creative reinterpretation of vibe or structure from a reference image. |
| guidances.image\_reference       | `array`   | References images to guide your video generation. Maximum 10 items. Each item includes image.id and image.type, and optionally order to control its position in the list of guidances.        |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`). Creative reinterpretation of vibe or structure from a reference image. |
| guidances.video\_reference\_base | `array`   | Base video to be edited. Maximum 5 items. Each item includes video.id and video.type (`GENERATED` or `UPLOADED`).                                                                             |
| guidances.webpage\_reference     | `array`   | A public webpage URL whose content guides the generation. Maximum 1 item. Each item includes webpage.url, which must be publicly accessible.                                                  |
| height                           | `number`  | Sets the height of the output video in pixels. Set to `0` to derive the height from `resolution`.                                                                                             |
| model                            | `string`  | Specifies the model used for generation. Set to `alibaba/wan-3.0`. Required.                                                                                                                  |
| motion\_has\_audio               | `boolean` | Whether the video generation will include audio. Defaults to `true`.                                                                                                                          |
| prompt                           | `string`  | Text description of the video content to generate. Maximum of 5000 characters. Required.                                                                                                      |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                     |
| quantity                         | `number`  | The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                                               |
| resolution                       | `string`  | Output resolution tier, used when `width` and `height` are automatic (`0`). Explicit dimensions take precedence. Valid values are `480p`, `720p`, and `1080p`. Defaults to `480p`.            |
| seed                             | `number`  | The seed value for generation. Supports `0` to `2147483647`.                                                                                                                                  |
| width                            | `number`  | Sets the width of the output video in pixels. Set to `0` to derive the width from `resolution`.                                                                                               |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio              | Pixel Values (Width x Height) |
| :--------- | :------------------------ | :---------------------------- |
| 480p       | 16:9 (Landscape)          | 854x480                       |
|            | 4:3                       | 736x552                       |
|            | 1:1 (Square)              | 640x640                       |
|            | 3:4                       | 552x736                       |
|            | 9:16 (Portrait)           | 480x854                       |
| 720p       | 16:9 (Landscape)          | 1280x720                      |
|            | 4:3                       | 1104x828                      |
|            | 1:1 (Square)              | 960x960                       |
|            | 3:4                       | 828x1104                      |
|            | 9:16 (Portrait)           | 720x1280                      |
| 1080p      | 16:9 (Landscape)          | 1920x1080                     |
|            | 4:3                       | 1656x1242                     |
|            | 1:1 (Square)              | 1440x1440                     |
|            | 3:4                       | 1242x1656                     |
|            | 9:16 (Portrait)           | 1080x1920                     |
| Automatic  | Derived from `resolution` | 0x0                           |