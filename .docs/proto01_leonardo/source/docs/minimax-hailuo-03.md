---
updatedAt: 2026-10-07T09:14:56.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# MiniMax Hailuo 03

This guide shows how to generate videos using the MiniMax Hailuo 03 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "model": "hailuo-03",
  "public": false,
  "parameters": {
    "prompt": "A koala and a cat playing together in a sunlit meadow",
    "quantity": 1,
    "width": 1376,
    "height": 768,
    "duration": 6,
    "quality": "TURBO",
    "motion_has_audio": true
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

| Parameter                        | Type      | Definition                                                                                                                                                                                                                                                                                            |
| :------------------------------- | :-------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | `integer` | *Optional.* Duration of the video in seconds. Accepts `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`. Defaults to `6`.                                                                                                                                                                   |
| guidances                        | `object`  | *Optional.* Object defining guidance inputs (e.g. start/end frames, reference images, reference videos, audio) that influence the result.                                                                                                                                                             |
| guidances.audio\_reference       | `array`   | *Optional.* Audio clips used as generation references. Maximum 3 items. Each item includes audio.id and audio.type (`UPLOADED`, `GENERATED`). Requires `guidances.image_reference` or `guidances.video_reference_base`; a start or end frame does not count. Not available when `quality` is `TURBO`. |
| guidances.end\_frame             | `array`   | *Optional.* Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, `BASE64`).                                                                                                |
| guidances.image\_reference       | `array`   | *Optional.* References images to guide your video generation. Maximum 9 items. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, `BASE64`), and an optional order.                                                                                             |
| guidances.start\_frame           | `array`   | *Optional.* Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, `BASE64`).                                                                                                |
| guidances.video\_reference\_base | `array`   | *Optional.* Base video to be edited. Maximum 3 items. Each item includes video.id, video.type (`UPLOADED`, `GENERATED`), and video.duration.                                                                                                                                                          |
| height                           | `integer` | *Optional.* Height of the output in pixels. Accepts `480`, `640`, `768`, `856`, `1024`, `1376`, `1440`, `1920`, `2160`, `2560`, `2880`, `3840`, `0`. Defaults to `768`. See [Dimensions](#dimensions) for valid width and height pairs.                                                               |
| model                            | `string`  | *Required.* Specifies the model used for generation. Set to `hailuo-03`.                                                                                                                                                                                                                              |
| motion\_has\_audio               | `boolean` | *Optional.* MiniMax Hailuo 03 always generates native audio; this cannot be disabled. Defaults to `true`.                                                                                                                                                                                             |
| prompt                           | `string`  | *Required.* The prompt to use for the generation. Maximum 7000 characters.                                                                                                                                                                                                                            |
| public                           | `boolean` | *Optional.* Controls whether the generation is public (`true`) or private (`false`).                                                                                                                                                                                                                  |
| quality                          | `string`  | *Optional.* Generation speed tier. Accepts `STANDARD`, `ACCELERATED`, `TURBO`. Defaults to `TURBO`.                                                                                                                                                                                                   |
| quantity                         | `integer` | *Required.* The number of outputs to generate. Defaults to `1`. Range 1-1.                                                                                                                                                                                                                            |
| resolution                       | `string`  | *Optional.* Output resolution used when `width` and `height` are `0` (automatic). Explicit `width` and `height` take precedence. Accepts `480p`, `768p`, `2k`, `4k`. Defaults to `768p`.                                                                                                              |
| width                            | `integer` | *Optional.* Width of the output in pixels. Accepts `480`, `640`, `768`, `856`, `1024`, `1120`, `1376`, `1440`, `1792`, `1920`, `2160`, `2560`, `2880`, `3360`, `3840`, `5040`, `0`. Defaults to `1376`. See [Dimensions](#dimensions) for valid width and height pairs.                               |

## Dimensions

The API accepts `width` and `height` parameters in the following combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 480p       | 21:9 (Landscape) | 1120 x 480                    |
|            | 16:9 (Landscape) | 856 x 480                     |
|            | 4:3 (Landscape)  | 640 x 480                     |
|            | 1:1 (Square)     | 480 x 480                     |
|            | 3:4 (Portrait)   | 480 x 640                     |
|            | 9:16 (Portrait)  | 480 x 856                     |
| 768p       | 21:9 (Landscape) | 1792 x 768                    |
|            | 16:9 (Landscape) | 1376 x 768                    |
|            | 4:3 (Landscape)  | 1024 x 768                    |
|            | 1:1 (Square)     | 768 x 768                     |
|            | 3:4 (Portrait)   | 768 x 1024                    |
|            | 9:16 (Portrait)  | 768 x 1376                    |
| 2K         | 21:9 (Landscape) | 3360 x 1440                   |
|            | 16:9 (Landscape) | 2560 x 1440                   |
|            | 4:3 (Landscape)  | 1920 x 1440                   |
|            | 1:1 (Square)     | 1440 x 1440                   |
|            | 3:4 (Portrait)   | 1440 x 1920                   |
|            | 9:16 (Portrait)  | 1440 x 2560                   |
| 4K         | 21:9 (Landscape) | 5040 x 2160                   |
|            | 16:9 (Landscape) | 3840 x 2160                   |
|            | 4:3 (Landscape)  | 2880 x 2160                   |
|            | 1:1 (Square)     | 2160 x 2160                   |
|            | 3:4 (Portrait)   | 2160 x 2880                   |
|            | 9:16 (Portrait)  | 2160 x 3840                   |
| Auto       | Auto             | 0 x 0                         |

Defaults to `1376` x `768`. Setting both `width` and `height` to `0` selects `Auto`; the output resolution is then set by the `resolution` parameter.