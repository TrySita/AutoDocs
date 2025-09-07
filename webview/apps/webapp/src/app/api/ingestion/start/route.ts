import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

// Input validation schema
const StartIngestionSchema = z.object({
  userId: z.string(),
  selections: z.object({
    github: z
      .object({
        account: z.string(),
        repos: z.array(
          z.object({
            id: z.string(),
            name: z.string(),
            fullName: z.string().optional(),
            description: z.string().nullable().optional(),
            private: z.boolean().optional(),
            url: z.string().optional(),
            defaultBranch: z.string().optional(),
            updatedAt: z.string().optional(),
          }),
        ),
      })
      .optional(),
    drive: z
      .object({
        account: z.string().email(),
        files: z.array(
          z.object({
            id: z.string(),
            name: z.string(),
            mimeType: z.string(),
            type: z.enum(["folder", "file"]),
            modifiedTime: z.string(),
            lastModified: z.string(),
            size: z.string().optional(),
            parents: z.array(z.string()).optional(),
            webViewLink: z.string().optional(),
            iconLink: z.string().optional(),
          }),
        ),
      })
      .optional(),
  }),
});

export async function POST(request: NextRequest) {
  try {
    // const body = await request.json();

    // // Validate input
    // const validatedInput = StartIngestionSchema.parse(body);

    // console.log(`Starting ingestion for user ${validatedInput.userId}`);
    // console.log("Ingestion input:", JSON.stringify(validatedInput, null, 2));

    // // Build the ingestion request
    // const ingestionRequest: IngestionRequest = IngestionRequestSchema.parse({
    //   userId: validatedInput.userId,
    //   github: validatedInput.selections.github,
    //   drive: validatedInput.selections.drive,
    // });

    // // Create the ingestion service
    // let ingestionService: IngestionService;
    // try {
    //   ingestionService = new IngestionService();
    // } catch (error) {
    //   console.error("Failed to initialize ingestion service:", error);
    //   return NextResponse.json(
    //     {
    //       success: false,
    //       message: `Ingestion service initialization failed: ${error instanceof Error ? error.message : "Unknown error"}`,
    //     },
    //     { status: 500 },
    //   );
    // }

    // // Process the ingestion asynchronously (fire and forget)
    // // We don't await this because we want to return immediately
    // ingestionService
    //   .processIngestion(ingestionRequest)
    //   .then((result) => {
    //     console.log(`Ingestion completed for user ${validatedInput.userId}:`, {
    //       jobId: result.jobId,
    //       status: result.status,
    //       itemCount: result.items.length,
    //       errors: result.errors?.length || 0,
    //     });
    //   })
    //   .catch((error) => {
    //     console.error(
    //       `Ingestion failed for user ${validatedInput.userId}:`,
    //       error,
    //     );
    //   });

    // Return immediately to not block the UI
    return NextResponse.json({
      success: true,
      message: "Ingestion started in background",
    });
  } catch (error) {
    console.error("Failed to start ingestion:", error);

    if (error instanceof z.ZodError) {
      return NextResponse.json(
        {
          success: false,
          message: "Invalid request data",
          errors: error.issues,
        },
        { status: 400 },
      );
    }

    return NextResponse.json(
      {
        success: false,
        message:
          error instanceof Error ? error.message : "Failed to start ingestion",
      },
      { status: 500 },
    );
  }
}
