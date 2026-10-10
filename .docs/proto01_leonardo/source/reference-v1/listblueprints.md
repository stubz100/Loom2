---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# List Blueprints

Returns a list of Blueprints. Use either forward pagination (first/after) or backward pagination (last/before), but not both. Note: This endpoint uses a request body to support complex filtering parameters

# OpenAPI definition

```json
{
  "openapi": "3.0.0",
  "info": {
    "description": "Leonardo.Ai API OpenAPI specification (v1.0).",
    "title": "Rest Endpoints",
    "version": "v1.0.0"
  },
  "servers": [
    {
      "url": "https://cloud.leonardo.ai/api/rest/v1",
      "description": "Leonardo.Ai API server"
    }
  ],
  "tags": [
    {
      "name": "Blueprints"
    }
  ],
  "paths": {
    "/blueprints": {
      "get": {
        "tags": [
          "Blueprints"
        ],
        "summary": "List Blueprints",
        "description": "Returns a list of Blueprints. Use either forward pagination (first/after) or backward pagination (last/before), but not both. Note: This endpoint uses a request body to support complex filtering parameters",
        "operationId": "listBlueprints",
        "requestBody": {
          "required": false,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "first": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "Number of items to return after the cursor (forward pagination)"
                  },
                  "after": {
                    "allOf": [
                      {
                        "$ref": "#/components/schemas/Cursor"
                      }
                    ],
                    "description": "Cursor to paginate forward from"
                  },
                  "last": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Number of items to return before the cursor (backward pagination)"
                  },
                  "before": {
                    "allOf": [
                      {
                        "$ref": "#/components/schemas/Cursor"
                      }
                    ],
                    "description": "Cursor to paginate backward from"
                  },
                  "platforms": {
                    "type": "array",
                    "items": {
                      "type": "string",
                      "enum": [
                        "Android",
                        "iOS",
                        "Web",
                        "API"
                      ]
                    },
                    "default": [
                      "API"
                    ],
                    "description": "Filter Blueprints by platforms that they can be executed on",
                    "example": [
                      "API",
                      "Web"
                    ]
                  },
                  "categories": {
                    "type": "array",
                    "items": {
                      "type": "string"
                    },
                    "description": "Filter Blueprints by category",
                    "example": [
                      "social-media"
                    ]
                  }
                }
              },
              "example": {
                "first": 10,
                "after": "eyJjcmVhdGVkQXQiOiIyMDI1LTEwLTI5VDIxOjMxOjQ3Ljk5OVoiLCJha1VVSUQiOiJjODQ2NDEzZS05MmJhLTQzMDItODRmOC00N2M2NjdkNDc2MWYifQ==",
                "platforms": [
                  "iOS",
                  "Android"
                ],
                "categories": [
                  "social-media"
                ]
              }
            }
          }
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "oneOf": [
                    {
                      "type": "object",
                      "properties": {
                        "blueprints": {
                          "type": "object",
                          "properties": {
                            "edges": {
                              "type": "array",
                              "items": {
                                "type": "object",
                                "properties": {
                                  "cursor": {
                                    "$ref": "#/components/schemas/Cursor"
                                  },
                                  "node": {
                                    "$ref": "#/components/schemas/Blueprint"
                                  }
                                }
                              }
                            },
                            "totalCount": {
                              "$ref": "#/components/schemas/totalCount"
                            },
                            "pageInfo": {
                              "$ref": "#/components/schemas/pageInfo"
                            }
                          }
                        }
                      },
                      "required": [
                        "blueprints"
                      ],
                      "description": "Successful response with Blueprint data"
                    },
                    {
                      "type": "array",
                      "items": {
                        "$ref": "#/components/schemas/ApiError"
                      },
                      "description": "Error response array"
                    }
                  ]
                },
                "examples": {
                  "success": {
                    "summary": "Successful response",
                    "value": {
                      "blueprints": {
                        "edges": [
                          {
                            "cursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTA3VDAzOjA4OjMwLjk3MVoiLCJha1VVSUQiOiJiM2VjN2VjZi1mYzYzLTRlZmMtODc0NS1mZGNmZDA1OWYwM2EifQ==",
                            "node": {
                              "akUUID": "b3ec7ecf-fc63-4efc-8745-fdcfd059f03a",
                              "createdAt": "2026-01-07T03:08:30.971Z",
                              "updatedAt": "2026-01-13T01:01:43.989Z",
                              "name": "Detailed Recipe with Tags",
                              "description": "Create an editorial photo of the dish with its ingredients around it and their names printed as physical labels.",
                              "thumbnails": [
                                {
                                  "name": "thumbnailUrl",
                                  "url": "https://cdn.dev.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/thumbnail-7357ab.webp"
                                },
                                {
                                  "name": "thumbnailUrlBanner",
                                  "url": "https://cdn.dev.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/thumbnail-1e754b.webp"
                                },
                                {
                                  "name": "thumbnailUrlLandscape",
                                  "url": "https://cdn.dev.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/thumbnail-d53597.webp"
                                },
                                {
                                  "name": "thumbnailUrlExtremePortrait",
                                  "url": "https://cdn.dev.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/thumbnail-1d8a28.webp"
                                }
                              ],
                              "teamId": null,
                              "official": true
                            }
                          }
                        ],
                        "totalCount": 1,
                        "pageInfo": {
                          "hasNextPage": false,
                          "hasPreviousPage": false,
                          "startCursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTA3VDAzOjA4OjMwLjk3MVoiLCJha1VVSUQiOiJiM2VjN2VjZi1mYzYzLTRlZmMtODc0NS1mZGNmZDA1OWYwM2EifQ==",
                          "endCursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTA3VDAzOjA4OjMwLjk3MVoiLCJha1VVSUQiOiJiM2VjN2VjZi1mYzYzLTRlZmMtODc0NS1mZGNmZDA1OWYwM2EifQ=="
                        }
                      }
                    }
                  },
                  "error": {
                    "summary": "Error response",
                    "value": [
                      {
                        "extensions": {
                          "code": "BadRequestException",
                          "details": {
                            "message": "Bad request. Please check your input.",
                            "statusCode": 400
                          }
                        },
                        "locations": [
                          {
                            "column": 97,
                            "line": 1
                          }
                        ],
                        "message": "An error occurred.",
                        "path": [
                          "blueprints"
                        ]
                      }
                    ]
                  }
                }
              }
            },
            "description": "Responses for GET /api/rest/v1/blueprints"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "Cursor": {
        "type": "string",
        "title": "Cursor",
        "description": "An opaque cursor used for pagination"
      },
      "Blueprint": {
        "type": "object",
        "title": "Blueprint",
        "description": "A Blueprint object",
        "properties": {
          "akUUID": {
            "type": "string",
            "description": "Unique identifier for the Blueprint",
            "example": "c846413e-92ba-4302-84f8-47c667d4761f"
          },
          "createdAt": {
            "type": "string",
            "format": "date-time",
            "description": "Creation timestamp",
            "example": "2025-10-29T21:31:47.999Z"
          },
          "updatedAt": {
            "type": "string",
            "format": "date-time",
            "description": "Last update timestamp",
            "example": "2025-12-19T02:34:44.740Z"
          },
          "name": {
            "type": "string",
            "description": "Name of the Blueprint",
            "example": "Golden Hour Relight"
          },
          "description": {
            "type": "string",
            "description": "Description of the Blueprint",
            "example": "Relight an image with warm, golden tones of late afternoon sunlight for a soft and radiant glow."
          },
          "thumbnails": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": {
                  "type": "string",
                  "description": "Thumbnail type name (e.g., thumbnailUrl, videoUrl, thumbnailUrlBanner, thumbnailUrlLandscape, thumbnailUrlExtremePortrait)",
                  "example": "thumbnailUrl"
                },
                "url": {
                  "type": "string",
                  "description": "URL of the thumbnail",
                  "example": "https://cdn.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/goldenhour.jpg"
                }
              }
            }
          },
          "teamId": {
            "type": "string",
            "nullable": true,
            "description": "Team ID if Blueprint belongs to a team",
            "example": null
          },
          "official": {
            "type": "boolean",
            "description": "Whether this is an official Blueprint",
            "example": true
          }
        }
      },
      "ApiError": {
        "type": "object",
        "title": "ApiError",
        "description": "API error response structure",
        "required": [
          "message"
        ],
        "properties": {
          "message": {
            "type": "string",
            "description": "Error message"
          },
          "path": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Path to the field that caused the error"
          },
          "locations": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "column": {
                  "type": "integer"
                },
                "line": {
                  "type": "integer"
                }
              }
            },
            "description": "Location information for the error"
          },
          "extensions": {
            "type": "object",
            "description": "Additional error details and context"
          }
        }
      },
      "pageInfo": {
        "type": "object",
        "title": "PageInfo",
        "description": "Pagination information following the Relay cursor pagination spec",
        "properties": {
          "hasNextPage": {
            "type": "boolean",
            "description": "Whether there is a next page"
          },
          "hasPreviousPage": {
            "type": "boolean",
            "description": "Whether there is a previous page"
          },
          "startCursor": {
            "allOf": [
              {
                "$ref": "#/components/schemas/Cursor"
              }
            ],
            "description": "Cursor for the first item in the result set"
          },
          "endCursor": {
            "allOf": [
              {
                "$ref": "#/components/schemas/Cursor"
              }
            ],
            "description": "Cursor for the last item in the result set"
          }
        }
      },
      "totalCount": {
        "type": "integer",
        "description": "Total number of results available"
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