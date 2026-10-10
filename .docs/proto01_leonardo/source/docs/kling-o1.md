---
updatedAt: 2026-02-10T00:31:58.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Kling O1

This guide shows how to generate video using Kling O1 model via the Leonardo.AI REST API.

This guide shows how to generate videos using **Kling O1** model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "kling-video-o-1",
    "public": false,
    "parameters": {
      "prompt": "The woman plays with the cat",
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
      "width": 1080,
      "height": 1920
    }
}
'
```

# Sample Request - Video Editing

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "model": "kling-video-o-1",
  "public": false,
  "parameters": {
    "prompt": "add @image1 to the background",
    "mode": "RESOLUTION_1080",
    "prompt_enhance": "OFF",
    "quantity": 1,
    "duration": 5,
    "seed": YOUR_SEED,
    "width": 1920,
    "height": 1080,
    "guidances": {
      "image_reference": [
        {
          "image": {
            "id": "YOUR_UPLOADED_IMAGE_ID",
            "type": "UPLOADED"
          }
        }
      ],
      "video_reference_base": [
        {
          "video": {
            "id": "YOUR_GENERATED_VIDEO_ID",
            "type": "GENERATED"
          }
        }
      ]
    }
  }
}
'
```

<br />

# Recipe

<Recipe slug="generate-with-kling-o1-using-start-and-end-frames" title="Generate with Kling O1 Using Start and End Frames" />

<Recipe slug="generate-with-kling-o1-using-image-references" title="Generate with Kling O1 Using Image References" />

<Recipe slug="video-editing-with-kling-o1-model" title="Video Editing with Image Reference using Kling O1 Model" />

<br />

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

<Table align={["left","left","left"]}>
  <thead>
    <tr>
      <th>
        Parameter
      </th>

      <th>
        Type
      </th>

      <th>
        Definition
      </th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>
        duration
      </td>

      <td>
        `number`
      </td>

      <td>
        Length of the generated video. Set to `5` or `10`.
      </td>
    </tr>

    <tr>
      <td>
        guidances.endframe
      </td>

      <td>
        `array`
      </td>

      <td>
        Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when `start_frame` is provided. Only available when NO `image_reference` is provided.
      </td>
    </tr>

    <tr>
      <td>
        guidances.image_reference
      </td>

      <td>
        `array`
      </td>

      <td>
        Array of up to four reference images used to guide the visual style or content of the generation. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when NO `start_frame` or `end_frame` is provided.
      </td>
    </tr>

    <tr>
      <td>
        guidances.start_frame
      </td>

      <td>
        `array`
      </td>

      <td>
        Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when NO `image_reference` is provided.
      </td>
    </tr>

    <tr>
      <td>
        guidances.video_reference_base
      </td>

      <td>
        `array`
      </td>

      <td>
        Duration of reference needs to be `3-10` seconds.

        Reference height/width needs to be at least `720`pixels. Width cannot be greater than `2160` pixels.

        Referenced videos can currently only be of `GENERATED` type.

        The video ID is the image ID of the associated image. i.e. the video is the video at `generated_images.motionMP4URL`
      </td>
    </tr>

    <tr>
      <td>
        height
      </td>

      <td>
        `number`
      </td>

      <td>
        Sets the height of the output video in pixels.
      </td>
    </tr>

    <tr>
      <td>
        model
      </td>

      <td>
        `string`
      </td>

      <td>
        Specifies the model used for generation. Set to `kling-video-o-1`.
      </td>
    </tr>

    <tr>
      <td>
        prompt
      </td>

      <td>
        `string`
      </td>

      <td>
        Text description of the video content to generate. Maximum of 1500 characters.
      </td>
    </tr>

    <tr>
      <td>
        public
      </td>

      <td>
        `boolean`
      </td>

      <td>
        Controls whether the generated video is public (true) or private (false).
      </td>
    </tr>

    <tr>
      <td>
        width
      </td>

      <td>
        `number`
      </td>

      <td>
        Sets the width of the output video in pixels.
      </td>
    </tr>
  </tbody>
</Table>

## Height and Width Combination

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Aspect Ratio     | Width | Height |
| :--------------- | :---- | :----- |
| 16:9 (Landscape) | 1920  | 1080   |
| 1:1 (Square)     | 1440  | 1440   |
| 9:16 (Portrait)  | 1080  | 1920   |