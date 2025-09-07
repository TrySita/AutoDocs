import { relations } from 'drizzle-orm/relations';
import {
  account,
  anonymousUsers,
  apikey,
  conversations,
  extensionTokens,
  invitation,
  member,
  messageLimits,
  messages,
  organization,
  publicProjects,
  repos,
  session,
  user,
} from './schema';

export const accountRelations = relations(account, ({ one }) => ({
  user: one(user, {
    fields: [account.userId],
    references: [user.id],
  }),
}));

export const userRelations = relations(user, ({ many }) => ({
  accounts: many(account),
  apikeys: many(apikey),
  conversations: many(conversations),
  extensionTokens: many(extensionTokens),
  invitations: many(invitation),
  messageLimits: many(messageLimits),
  members: many(member),
  sessions: many(session),
}));

export const apikeyRelations = relations(apikey, ({ one }) => ({
  user: one(user, {
    fields: [apikey.userId],
    references: [user.id],
  }),
}));

export const conversationsRelations = relations(conversations, ({ one, many }) => ({
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
}));

export const anonymousUsersRelations = relations(anonymousUsers, ({ many }) => ({
  conversations: many(conversations),
  messageLimits: many(messageLimits),
}));

export const publicProjectsRelations = relations(publicProjects, ({ many }) => ({
  conversations: many(conversations),
}));

export const extensionTokensRelations = relations(extensionTokens, ({ one }) => ({
  user: one(user, {
    fields: [extensionTokens.userId],
    references: [user.id],
  }),
}));

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

export const messagesRelations = relations(messages, ({ one }) => ({
  conversation: one(conversations, {
    fields: [messages.conversationId],
    references: [conversations.id],
  }),
}));

export const sessionRelations = relations(session, ({ one }) => ({
  user: one(user, {
    fields: [session.userId],
    references: [user.id],
  }),
}));

export const reposRelations = relations(repos, ({ one }) => ({
  organization: one(organization, {
    fields: [repos.organizationId],
    references: [organization.id],
  }),
}));
