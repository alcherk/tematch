-- Add reply_to_msg_id column to messages table for thread/reply chain support
ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply_to_msg_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_messages_reply_to_msg_id ON messages (reply_to_msg_id);
