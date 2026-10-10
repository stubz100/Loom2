---
updatedAt: 2026-01-21T05:03:25.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Guide to Handling Not Safe for Work Image Generation (NSFW)

# Blocking at the Prompt Level

Like the Leonardo web app, the Leonardo API will block NSFW image generation by default. Any prompts flagged as NSFW will return a 400 Bad Request error.

For example, generating with a prompt “nude” will be blocked with the following error:

```
{  
  "error": "content moderation filter: nude",  
  "path": "$",  
  "code": "unexpected"  
}
```

# Flagging at the Response Level

The Production API returns a NSFW attribute that flags if the image generated contains NSFW material. Depending on your use case, you can opt to filter out the flagged images and not return them to your end users.

```
...
"generated_images": \[  
      {  
        "url": "<https://cdn.leonardo.ai/users/ef8b8386-94f7-48d1-b10e-e87fd4dee6e6/generations/88b381ea-7baf-457d-a5b4-8068cb6bac21/Leonardo_Creative_An_oil_painting_of_a_cat_0.jpg">,  
        "nsfw": true,  
        "id": "5b710f5f-22de-4d27-8b5c-4eadc98bfc85",  
        "likeCount": 0,  
        "generated_image_variation_generics": \[]  
      },
      ...
]
...
```

If you’d like more rigid NSFW controls, please [contact us](https://leonardo.ai/contact-us/) for assistance, letting us know about your use case and requirements.

# Adding your own Image Moderation Layer

For use cases that require more control over the images generated, we recommend adding your own image moderation layer. You can implement your own system, leverage a more specialised third-party detection system, and/or keep a human in the loop to check against your guidelines.