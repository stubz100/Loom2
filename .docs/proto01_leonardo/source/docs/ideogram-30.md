---
updatedAt: 2026-06-29T01:25:37.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Ideogram 3.0

This guide shows how to generate images using Ideogram 3.0 model via the Leonardo.AI REST API.

<Callout icon="⚠️" theme="warn">
  ###

  Deprecation Notice – mode parameter The mode parameter is being deprecated and will no longer be supported from May 4, 2026. Please update your requests to use the quality parameter instead. After May 4th, any requests that include mode will return a validation error and fail. What you need to do: Replace 'mode' with 'quality' in your API requests for GPT 1.5 and Ideogram generations before May 4th to avoid service disruption.

  You can find the migration example in [Deprecations & Changes](https://docs.leonardo.ai/docs/deprecations-changes#april-20-2026--mode-parameter-retiring-may-4-2026) page
</Callout>

This guide shows how to generate images using Ideogram 3.0 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '{
       "model": "ideogram-v3.0",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "A dynamically stylish green running shoe dominates the frame, with the text Leonardo, the text boldly emblazoned in white. Against a vivid blue backdrop, the shoe exudes modernity with a hint of motion blur, conveying speed and dynamism. Crisp lines and vibrant hues are subtly softened, capturing the essence of movement",
           "quality": "MEDIUM",
           "quantity": 2,
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ]
       },
       "public": false
   }'
```

# Recipe

<Recipe slug="generate-images-using-ideogram-30" title="Generate Images Using Ideogram 3.0" />

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

| Parameter       | Type      | Definition                                                                                               |
| :-------------- | :-------- | :------------------------------------------------------------------------------------------------------- |
| height          | `integer` | *Optional.* Height input resolution.                                                                     |
| model           | `string`  | *Required.* Model identifier. Set to `ideogram-v3.0`                                                     |
| prompt          | `string`  | *Required.* Text prompt describing what image you want the model to generate.                            |
| prompt\_enhance | `string`  | *Optional.* Enables prompt enhancement when set to `"ON"`; disabled when set to `"OFF"`.                 |
| public          | `boolean` | *Optional.* Boolean flag that determines whether the generation is public (`true`) or private (`false`). |
| quantity        | `integer` | *Optional.* Number of images to generate in a single request.                                            |
| seed            | `integer` | *Optional.* Apply a fixed seed to maintain consistency across generation sets.                           |
| style\_ids      | `array`   | *Optional.* Array of style UUIDs used to apply preset artistic styles to the output.                     |
| width           | `integer` | *Optional.* Width input resolution.                                                                      |
| quality         | `string`  | *Optional.* Accepts `TURBO`, `BALANCED`, or `QUALITY`.                                                   |

## List of Style IDs

| Preset Style | UUID                                   |
| ------------ | -------------------------------------- |
| Cinematic    | `a5632c7c-ddbb-4e2f-ba34-8456ab3ac436` |
| Creative     | `6fedbf1f-4a17-45ec-84fb-92fe524a29ef` |
| Dynamic      | `111dc692-d470-4eec-b791-3475abac4c46` |
| Fashion      | `594c4a08-a522-4e0e-b7ff-e4dac4b6b622` |
| Portrait     | `ab5a4220-7c42-41e5-a578-eddb9fed3d75` |
| Stock Photo  | `5bdc3f2a-1be6-4d1c-8e77-992a30824a2c` |
| Vibrant      | `dee282d3-891f-4f73-ba02-7f8131e5541b` |

<br />

<br />

<br />