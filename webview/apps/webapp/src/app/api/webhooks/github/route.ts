import crypto from "crypto";
import { headers } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

// Webhook event schemas
const RepositoryEventSchema = z.object({
  action: z.string(),
  repository: z.object({
    id: z.number(),
    name: z.string(),
    full_name: z.string(),
    private: z.boolean(),
    owner: z.object({
      login: z.string(),
      id: z.number(),
    }),
  }),
  sender: z.object({
    login: z.string(),
    id: z.number(),
  }),
});

const PushEventSchema = z.object({
  ref: z.string(),
  commits: z.array(
    z.object({
      id: z.string(),
      message: z.string(),
      author: z.object({
        name: z.string(),
        email: z.string(),
      }),
    }),
  ),
  repository: z.object({
    id: z.number(),
    name: z.string(),
    full_name: z.string(),
  }),
});

const InstallationEventSchema = z.object({
  action: z.enum([
    "created",
    "deleted",
    "suspend",
    "unsuspend",
    "new_permissions_accepted",
  ]),
  installation: z.object({
    id: z.number(),
    account: z.object({
      login: z.string(),
      type: z.string(),
    }),
  }),
  repositories: z
    .array(
      z.object({
        id: z.number(),
        name: z.string(),
        full_name: z.string(),
      }),
    )
    .optional(),
});

// Verify webhook signature
function verifyWebhookSignature(
  payload: string,
  signature: string | null,
  secret: string,
): boolean {
  if (!signature) return false;

  const hmac = crypto.createHmac("sha256", secret);
  hmac.update(payload);
  const expectedSignature = `sha256=${hmac.digest("hex")}`;

  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSignature),
  );
}

export async function POST(request: NextRequest) {
  try {
    const webhookSecret = process.env.GITHUB_WEBHOOK_SECRET;

    if (!webhookSecret) {
      console.error("GitHub webhook secret not configured");
      return NextResponse.json(
        { error: "Webhook not configured" },
        { status: 500 },
      );
    }

    // Get headers
    const headersList = await headers();
    const signature = headersList.get("x-hub-signature-256");
    const githubEvent = headersList.get("x-github-event");
    const deliveryId = headersList.get("x-github-delivery");

    // Get raw body for signature verification
    const rawBody = await request.text();

    // Verify signature
    if (!verifyWebhookSignature(rawBody, signature, webhookSecret)) {
      console.error("Invalid webhook signature");
      return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
    }

    // Parse JSON body
    const body = JSON.parse(rawBody);

    console.log(`Received GitHub webhook: ${githubEvent} (${deliveryId})`);

    // Handle different event types
    switch (githubEvent) {
      case "installation":
      case "installation_repositories":
        await handleInstallationEvent(body);
        break;

      case "push":
        await handlePushEvent(body);
        break;

      case "repository":
        await handleRepositoryEvent(body);
        break;

      case "pull_request":
        await handlePullRequestEvent(body);
        break;

      case "issues":
        await handleIssuesEvent(body);
        break;

      case "ping":
        console.log("Received ping event from GitHub");
        return NextResponse.json({ message: "pong" });

      default:
        console.log(`Unhandled webhook event: ${githubEvent}`);
    }

    return NextResponse.json({ received: true });
  } catch (error) {
    console.error("Webhook processing error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 },
    );
  }
}

// Event handlers
async function handleInstallationEvent(payload: any) {
  try {
    const event = InstallationEventSchema.parse(payload);

    console.log(
      `Installation ${event.action}: ${event.installation.account.login}`,
    );

    // Store installation info in database
    if (event.action === "created") {
      // TODO: Store installation ID and associated repositories
      // This allows you to make API calls on behalf of the installation

      const installationData = {
        installationId: event.installation.id,
        accountLogin: event.installation.account.login,
        accountType: event.installation.account.type,
        repositories: event.repositories || [],
        createdAt: new Date(),
      };
    } else if (event.action === "deleted") {
      // TODO: Clean up installation data
    }
  } catch (error) {
    console.error("Error handling installation event:", error);
  }
}

async function handlePushEvent(payload: any) {
  try {
    const event = PushEventSchema.parse(payload);

    // You could trigger analysis or notifications here
    const pushData = {
      repository: event.repository.full_name,
      branch: event.ref.replace("refs/heads/", ""),
      commits: event.commits.map((c) => ({
        id: c.id,
        message: c.message,
        author: c.author.name,
      })),
      timestamp: new Date(),
    };
  } catch (error) {
    console.error("Error handling push event:", error);
  }
}

async function handleRepositoryEvent(payload: any) {
  try {
    const event = RepositoryEventSchema.parse(payload);

    // Handle repository changes
    if (event.action === "deleted") {
      // TODO: Clean up repository data
    } else if (event.action === "privatized" || event.action === "publicized") {
      // TODO: Update repository visibility
    }
  } catch (error) {
    console.error("Error handling repository event:", error);
  }
}

async function handlePullRequestEvent(payload: any) {
  try {
    const { action, pull_request, repository } = payload;

    console.log(
      `Pull request ${action} in ${repository.full_name}: #${pull_request.number}`,
    );

    // You could trigger PR analysis or notifications here
    if (action === "opened" || action === "synchronize") {
      const prData = {
        repository: repository.full_name,
        number: pull_request.number,
        title: pull_request.title,
        author: pull_request.user.login,
        action,
        timestamp: new Date(),
      };
    }
  } catch (error) {
    console.error("Error handling pull request event:", error);
  }
}

async function handleIssuesEvent(payload: any) {
  try {
    const { action, issue, repository } = payload;

    if (action === "opened") {
      const issueData = {
        repository: repository.full_name,
        number: issue.number,
        title: issue.title,
        author: issue.user.login,
        timestamp: new Date(),
      };

      // TODO: Process issue event (e.g., auto-label, notify team)
    }
  } catch (error) {
    console.error("Error handling issues event:", error);
  }
}

// Health check endpoint
export async function GET() {
  return NextResponse.json({
    status: "ok",
    webhook: "github",
    timestamp: new Date().toISOString(),
  });
}
