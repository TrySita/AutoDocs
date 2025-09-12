import { relations } from "drizzle-orm/relations";
import {
  user,
  apikey,
  extensionTokens,
  invitation,
  organization,
  member,
  anonymousUsers,
  messageLimits,
  account,
  conversations,
  publicProjects,
  messages,
  repos,
  session,
} from "./schema";

export const apikeyRelations = relations(apikey, ({ one }) => ({
  user: one(user, {
    fields: [apikey.userId],
    references: [user.id],
  }),
}));

export const userRelations = relations(user, ({ many }) => ({
  apikeys: many(apikey),
  extensionTokens: many(extensionTokens),
  invitations: many(invitation),
  members: many(member),
  messageLimits: many(messageLimits),
  accounts: many(account),
  conversations: many(conversations),
  sessions: many(session),
}));

export const extensionTokensRelations = relations(
  extensionTokens,
  ({ one }) => ({
    user: one(user, {
      fields: [extensionTokens.userId],
      references: [user.id],
    }),
  })
);

export const invitationRelations = relations(invitation, ({ one }) => ({
  user: one(user, {
    fields: [invitation.inviterId],
    references: [user.id],
  }),
  organization: one(organization, {
    fields: [invitation.organizationId],
    references: [organization.id],
  }),
}));

export const organizationRelations = relations(organization, ({ many }) => ({
  invitations: many(invitation),
  members: many(member),
  repos: many(repos),
}));

export const memberRelations = relations(member, ({ one }) => ({
  organization: one(organization, {
    fields: [member.organizationId],
    references: [organization.id],
  }),
  user: one(user, {
    fields: [member.userId],
    references: [user.id],
  }),
}));

export const messageLimitsRelations = relations(messageLimits, ({ one }) => ({
  anonymousUser: one(anonymousUsers, {
    fields: [messageLimits.anonymousUserId],
    references: [anonymousUsers.id],
  }),
  user: one(user, {
    fields: [messageLimits.userId],
    references: [user.id],
  }),
}));

export const anonymousUsersRelations = relations(
  anonymousUsers,
  ({ many }) => ({
    messageLimits: many(messageLimits),
    conversations: many(conversations),
  })
);

export const accountRelations = relations(account, ({ one }) => ({
  user: one(user, {
    fields: [account.userId],
    references: [user.id],
  }),
}));

export const conversationsRelations = relations(
  conversations,
  ({ one, many }) => ({
    anonymousUser: one(anonymousUsers, {
      fields: [conversations.anonymousUserId],
      references: [anonymousUsers.id],
    }),
    publicProject: one(publicProjects, {
      fields: [conversations.projectId],
      references: [publicProjects.id],
    }),
    user: one(user, {
      fields: [conversations.userId],
      references: [user.id],
    }),
    messages: many(messages),
  })
);

export const publicProjectsRelations = relations(
  publicProjects,
  ({ many }) => ({
    conversations: many(conversations),
  })
);

export const messagesRelations = relations(messages, ({ one }) => ({
  conversation: one(conversations, {
    fields: [messages.conversationId],
    references: [conversations.id],
  }),
}));

export const reposRelations = relations(repos, ({ one }) => ({
  organization: one(organization, {
    fields: [repos.organizationId],
    references: [organization.id],
  }),
}));

export const sessionRelations = relations(session, ({ one }) => ({
  user: one(user, {
    fields: [session.userId],
    references: [user.id],
  }),
}));
