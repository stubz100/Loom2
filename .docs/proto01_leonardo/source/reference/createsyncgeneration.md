---
updatedAt: 2026-08-31T05:44:48.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Create Sync Generation

Run a generation and return the finished result in the same response. Only sync-capable models are accepted. The request may take up to ~27 seconds before the service times out.

# OpenAPI definition

```json
{
  "x-generated-notice": "AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY. Edit openapi-v2.template.json instead, then run: npm run generate:v2-models",
  "openapi": "3.0.0",
  "info": {
    "description": "Leonardo.Ai API OpenAPI specification v2.0",
    "title": "Rest Endpoints v2",
    "version": "v2.0.0"
  },
  "servers": [
    {
      "url": "https://cloud.leonardo.ai/api/rest/v2",
      "description": "Leonardo.Ai API server v2"
    }
  ],
  "tags": [
    {
      "name": "Generations"
    }
  ],
  "paths": {
    "/generationssync": {
      "post": {
        "tags": [
          "Generations"
        ],
        "summary": "Create Sync Generation",
        "description": "Run a generation and return the finished result in the same response. Only sync-capable models are accepted. The request may take up to ~27 seconds before the service times out.",
        "operationId": "createSyncGeneration",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "discriminator": {
                  "propertyName": "model",
                  "mapping": {
                    "remove-bg": "#/components/schemas/RemoveBgSyncGenerationRequest"
                  }
                },
                "oneOf": [
                  {
                    "$ref": "#/components/schemas/RemoveBgSyncGenerationRequest"
                  }
                ]
              }
            }
          },
          "description": "Request body for a synchronous generation",
          "required": true
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/SyncGenerationResponse"
                }
              }
            },
            "description": "Responses for POST /generationssync"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "Cost": {
        "title": "Cost",
        "type": "object",
        "required": [
          "amount",
          "unit"
        ],
        "properties": {
          "amount": {
            "type": "string",
            "description": "The cost amount (credits or dollars, depending on `unit`). Serialized from the Decimal scalar."
          },
          "unit": {
            "type": "string",
            "enum": [
              "CREDITS",
              "DOLLARS"
            ],
            "description": "Whether `amount` is API credits or dollars."
          }
        }
      },
      "SyncGenerationResult": {
        "title": "Sync generation result",
        "type": "object",
        "required": [
          "contentType"
        ],
        "properties": {
          "contentType": {
            "type": "string",
            "description": "Media type of the generated image (for example `image/png`)."
          },
          "url": {
            "type": "string",
            "format": "uri",
            "description": "CDN URL of the stored image, or a 30-minute presigned URL when `ephemeral` is true. Omitted when `base64` is true."
          },
          "dataB64": {
            "type": "string",
            "format": "byte",
            "description": "Base64-encoded image bytes. Present only when the request set `base64` to true."
          },
          "width": {
            "type": "integer",
            "description": "Output width in pixels, when reported by the provider."
          },
          "height": {
            "type": "integer",
            "description": "Output height in pixels, when reported by the provider."
          }
        }
      },
      "SyncGenerationResponse": {
        "title": "Sync generation response",
        "type": "object",
        "required": [
          "id",
          "results",
          "blockedCount"
        ],
        "properties": {
          "id": {
            "type": "string",
            "description": "Generation identifier."
          },
          "cost": {
            "allOf": [
              {
                "$ref": "#/components/schemas/Cost"
              }
            ],
            "description": "Cost charged for this generation. Present for Production API users."
          },
          "results": {
            "type": "array",
            "description": "One entry per output that passed moderation, in provider order.",
            "items": {
              "$ref": "#/components/schemas/SyncGenerationResult"
            }
          },
          "blockedCount": {
            "type": "integer",
            "description": "Number of outputs withheld by content moderation."
          }
        }
      },
      "RemoveBgSyncGenerationRequest": {
        "title": "Remove Background (sync)",
        "type": "object",
        "required": [
          "model"
        ],
        "properties": {
          "model": {
            "type": "string",
            "enum": [
              "remove-bg"
            ],
            "description": "Must be `remove-bg`."
          },
          "public": {
            "type": "boolean",
            "description": "Whether the generated images should show in the community feed. Ignored when `ephemeral` is true."
          },
          "parameters": {
            "type": "object",
            "required": [
              "guidances"
            ],
            "properties": {
              "roi": {
                "type": "string",
                "description": "Region of interest to search for the subject, given as two x/y coordinate pairs in pixels ('0px 0px 100px 100px') or percentages ('0% 0% 100% 100%'). Anything outside this rectangle is treated as background."
              },
              "crop": {
                "type": "boolean",
                "default": false,
                "description": "Crops the output image to the bounding box of the subject."
              },
              "size": {
                "enum": [
                  "auto",
                  "preview",
                  "full",
                  "50MP"
                ],
                "type": "string",
                "anyOf": [
                  {
                    "enum": [
                      "preview"
                    ]
                  },
                  {
                    "enum": [
                      "auto"
                    ]
                  },
                  {
                    "enum": [
                      "full"
                    ]
                  },
                  {
                    "enum": [
                      "50MP"
                    ]
                  }
                ],
                "default": "full",
                "description": "Maximum output image resolution. 'preview' caps at 0.25 megapixels, 'full' and 'auto' cap at 25 megapixels, and '50MP' allows up to 50 megapixels. PNG output is capped at 10 megapixels regardless of this setting."
              },
              "type": {
                "enum": [
                  "auto",
                  "person",
                  "product",
                  "car",
                  "animal",
                  "graphic",
                  "transportation",
                  "other"
                ],
                "type": "string",
                "default": "auto",
                "description": "Foreground type hint to improve cutout quality."
              },
              "scale": {
                "type": "string",
                "description": "Scale of the subject relative to the output canvas, as 'original' or a percentage between '10%' and '100%'."
              },
              "format": {
                "enum": [
                  "png",
                  "jpg",
                  "webp"
                ],
                "type": "string",
                "default": "png",
                "description": "Output image format. PNG and WebP preserve transparency, JPG does not. PNG is capped at 10 megapixels by the provider, so pair larger 'size' values with WebP to keep transparency. remove.bg's 'auto' is deliberately not offered: it picks PNG or JPG from the finished pixels, and the output's storage key has to be named before the request is sent."
              },
              "bg_color": {
                "type": "string",
                "description": "Adds a solid background color to the cutout (hex code or color name). Output is no longer transparent — pair with 'jpg' when possible."
              },
              "channels": {
                "enum": [
                  "rgba",
                  "alpha"
                ],
                "type": "string",
                "default": "rgba",
                "description": "'rgba' returns the cutout image; 'alpha' returns only the greyscale alpha mask."
              },
              "position": {
                "type": "string",
                "description": "Position of the subject within the output canvas, as 'original', 'center', a single percentage, or two percentages for horizontal and vertical placement."
              },
              "quantity": {
                "type": "integer",
                "default": 1,
                "maximum": 1,
                "minimum": 1,
                "description": "Number of outputs to generate (fixed at 1)"
              },
              "guidances": {
                "type": "object",
                "title": "Image guidance",
                "description": "The image guidance properties object that will be defined on a per-model basis.",
                "required": [
                  "image_reference"
                ],
                "properties": {
                  "image_reference": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "title": "Image reference",
                      "required": [
                        "image"
                      ],
                      "properties": {
                        "image": {
                          "type": "object",
                          "allOf": [
                            {},
                            {}
                          ],
                          "title": "Image reference",
                          "properties": {
                            "id": {
                              "type": "string",
                              "format": "uuid"
                            },
                            "url": {
                              "type": "string",
                              "format": "uri",
                              "description": "Image URL or a base64 data URL. Required when type is URL. The backend enriches resolved image URLs."
                            },
                            "data": {
                              "type": "string",
                              "description": "Base64-encoded image bytes. Required when type is BASE64.",
                              "format": "byte"
                            },
                            "type": {
                              "enum": [
                                "UPLOADED",
                                "GENERATED",
                                "VARIATION",
                                "URL",
                                "BASE64"
                              ],
                              "type": "string"
                            },
                            "width": {
                              "type": "integer"
                            },
                            "height": {
                              "type": "integer"
                            }
                          },
                          "description": "A reference to an image"
                        },
                        "order": {
                          "type": "integer",
                          "title": "GuidanceOrder",
                          "minimum": 0,
                          "description": "The order at which we want this guidance to be in a list of guidances"
                        }
                      },
                      "description": "Image reference guidance object, containing parameters available for image reference guidance"
                    },
                    "title": "Image Reference",
                    "description": "References images to guide your video generation.",
                    "maxItems": 1,
                    "minItems": 1
                  },
                  "background_image_reference": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "title": "Image reference",
                      "required": [
                        "image"
                      ],
                      "properties": {
                        "image": {
                          "type": "object",
                          "allOf": [
                            {},
                            {}
                          ],
                          "title": "Image reference",
                          "properties": {
                            "id": {
                              "type": "string",
                              "format": "uuid"
                            },
                            "url": {
                              "type": "string",
                              "format": "uri",
                              "description": "Image URL or a base64 data URL. Required when type is URL. The backend enriches resolved image URLs."
                            },
                            "data": {
                              "type": "string",
                              "description": "Base64-encoded image bytes. Required when type is BASE64.",
                              "format": "byte"
                            },
                            "type": {
                              "enum": [
                                "UPLOADED",
                                "GENERATED",
                                "VARIATION",
                                "URL",
                                "BASE64"
                              ],
                              "type": "string"
                            },
                            "width": {
                              "type": "integer"
                            },
                            "height": {
                              "type": "integer"
                            }
                          },
                          "description": "A reference to an image"
                        },
                        "order": {
                          "type": "integer",
                          "title": "GuidanceOrder",
                          "minimum": 0,
                          "description": "The order at which we want this guidance to be in a list of guidances"
                        }
                      },
                      "description": "Image reference guidance object, containing parameters available for image reference guidance"
                    },
                    "maxItems": 1,
                    "minItems": 1,
                    "description": "An existing Leo image to composite behind the cutout, replacing the removed background. Omit to keep the background transparent (or a solid color via 'bg_color')."
                  }
                }
              },
              "type_level": {
                "enum": [
                  "none",
                  "1",
                  "2",
                  "latest"
                ],
                "type": "string",
                "description": "How specifically the subject should be classified. 'none' skips classification, '1' picks a coarse category, '2' picks a specific category, and 'latest' uses the most detailed classification available."
              },
              "crop_margin": {
                "type": "string",
                "description": "Margin to add around the cropped subject, as an absolute value ('30px') or relative to the subject size ('10%'). Accepts one, two, or four values and only applies when 'crop' is enabled."
              },
              "shadow_type": {
                "enum": [
                  "none",
                  "drop",
                  "3d",
                  "car"
                ],
                "type": "string",
                "default": "none",
                "description": "Style of artificial shadow to render under the subject."
              },
              "shadow_opacity": {
                "type": "integer",
                "maximum": 100,
                "minimum": 0,
                "description": "Opacity of the artificial shadow, from 0 to 100. Only applies when a shadow is enabled."
              },
              "semitransparency": {
                "type": "boolean",
                "default": true,
                "description": "Preserves semi-transparent regions such as glass, smoke, and veils."
              }
            },
            "description": "Architecture properties of the Remove Background model",
            "additionalProperties": false
          },
          "ephemeral": {
            "type": "boolean",
            "default": false,
            "description": "When true, the result is not persisted to the library and the response URL is a 30-minute presigned GET."
          },
          "base64": {
            "type": "boolean",
            "default": false,
            "description": "When true, return results[].dataB64 instead of results[].url. The request fails if the encoded payload would exceed the response size limit."
          }
        },
        "example": {
          "model": "remove-bg",
          "parameters": {
            "size": "full",
            "channels": "rgba",
            "quantity": 1,
            "guidances": "your guidances here",
            "shadow_type": "none",
            "semitransparency": true
          }
        }
      }
    },
    "securitySchemes": {
      "bearerAuth": {
        "type": "http",
        "bearerFormat": "auth-scheme",
        "description": "Bearer HTTP authentication. Allowed headers `Authorization: Bearer <api_key>`",
        "scheme": "bearer"
      }
    }
  },
  "security": [
    {
      "bearerAuth": []
    }
  ]
}
```