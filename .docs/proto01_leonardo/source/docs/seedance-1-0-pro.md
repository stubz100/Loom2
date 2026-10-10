---
updatedAt: 2026-01-23T02:53:20.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedance 1.0 Pro

This guide shows how to generate images using Seedance 1.0 Pro and Seedance 1.0 Pro Fast models via the Leonardo.AI REST API.

This guide shows how to generate images using **Seedance 1.0 Pro** and **Seedance 1.0 Pro Fast** models via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "seedance-1.0-pro",
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
      "duration": 4,
      "mode": "RESOLUTION_1080",
      "prompt_enhance": "OFF",
      "width": 1920,
      "height": 1088
    }
}
'
```

# Recipe

<Recipe slug="generate-with-seedance-10-pro-using-start-and-end-frames" title="Generate with SeeDance 1.0 Pro Using Start and End Frames" />

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

| Parameter              | Type      | Definition                                                                                                                             |
| :--------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------- |
| duration               | `number`  | Length of the generated video. Set to `4`, `6`, `8`, `10`.                                                                             |
| guidances.endframe     | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when `start_frame` is provided. |
| guidances.start\_frame | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`).                                                |
| height                 | `number`  | Sets the height of the output video in pixels.                                                                                         |
| model                  | `string`  | Specifies the model used for generation. Set to `seedance-1.0-pro` or `seedance-1.0-pro-fast`                                          |
| prompt                 | `string`  | Text description of the video content to generate. Maximum of 1500 characters.                                                         |
| prompt\_enhance        | `string`  | Enables or disables prompt enhancement. Valid values are `ON` and `OFF`.                                                               |
| public                 | `boolean` | Controls whether the generated video is public (true) or private (false).                                                              |
| width                  | `number`  | Sets the width of the output video in pixels.                                                                                          |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

<Table align={["left","left","left"]}>
  <thead>
    <tr>
      <th>
        Resolution
      </th>

      <th>
        Aspect Ratio
      </th>

      <th>
        Pixel Values (Width x Height)
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        480p
      </td>

      <td>
        16:9 (Landscape)
      </td>

      <td>
        864x480
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        4:3
      </td>

      <td>
        736x544
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        1:1 (Square)
      </td>

      <td>
        640x640
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        3:4
      </td>

      <td>
        544x736
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        9:16 (Portrait)
      </td>

      <td>
        480x864
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        21:9
      </td>

      <td>
        960x416
      </td>
    </tr>

    <tr>
      <td>
        720p
      </td>

      <td>
        16:9 (Landscape)
      </td>

      <td>
        1248x704
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        4:3
      </td>

      <td>
        1120x832
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        1:1 (Square)
      </td>

      <td>
        960x960
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        3:4
      </td>

      <td>
        832x1120
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        9:16 (Portrait)
      </td>

      <td>
        704x1248
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        21:9
      </td>

      <td>
        1504x640
      </td>
    </tr>

    <tr>
      <td>
        1080p  
        (Reference Image feature is not supported)
      </td>

      <td>
        16:9 (Landscape)
      </td>

      <td>
        1920x1088
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        4:3
      </td>

      <td>
        1664x1248
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        1:1 (Square)
      </td>

      <td>
        1440x1440
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        3:4
      </td>

      <td>
        1248x1664
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        9:16 (Portrait)
      </td>

      <td>
        1088x1920
      </td>
    </tr>

    <tr>
      <td>

      </td>

      <td>
        21:9
      </td>

      <td>
        2176x928
      </td>
    </tr>
  </tbody>
</Table>