---
updatedAt: 2026-07-01T04:01:40.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Concurrency, Rate Limits, Queue

<Callout icon="📘" theme="info">
  ### Need more concurrency? Need to increase rate limits?

  Please [contact us](https://leonardo.ai/contact-us/) for assistance, letting us know about your use case and requirements.
</Callout>

# Concurrency

| Description                              | Limit        |
| :--------------------------------------- | :----------- |
| Concurrent image generation job          | 10 (Default) |
| Concurrent Blueprints execution job      | 10 (Default) |
| Concurrent model training generation job | 5 (Default)  |
| Concurrent 3D generation job             | 10 (Default) |

**Note:**

* Default concurrency can be increased on a custom API plan.

# API Rate Limits

| Request Type                             | Endpoint                          | Limit                     |
| :--------------------------------------- | :-------------------------------- | :------------------------ |
| All request types                        | All                               | 2000 per minute (Default) |
| Create a Generation of Images requests   | /v1/generations                   | 100 per minute (Default)  |
| Create using Universal Upscaler requests | /v1/variations/universal-upscaler | 100 per minute (Default)  |
| Create unzoom requests                   | /v1/variations/unzoom             | 100 per minute (Default)  |
| Create upscale requests                  | /v1/variations/upscale            | 100 per minute (Default)  |
| Create no background requests            | /v1/variations/nobg               | 100 per minute (Default)  |
| Create Texture Generation requests       | /v1/generations-texture           | 100 per minute (Default)  |
| Execute Blueprints                       | /v1/blueprint-executions          | 100 per minute (Default)  |
| Create a 3D Generation requests          | /v2/generations                   | 100 per minute (Default)  |

<br />

**Note:**

* 1 concurrency comes with 10 generation requests (applies to image, 3D, and other V2 endpoint generation types).

# Queue Limit

| Description                                      | Limit         |
| :----------------------------------------------- | :------------ |
| Image generation with status pending / queued    | 200 (Default) |
| Upscaling with status pending / queued           | 100 (Default) |
| Blueprints executed with status pending / queued | 10 (Default)  |
| 3D generation with status pending / queued       | 100 (Default) |

**Note:**

* 1 concurrency comes with 20 image generation with status pending
* 1 concurrency comes with 10 3D generation with status pending.

<br />