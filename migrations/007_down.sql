-- DOWN Migration 007: Revert Property Graph to Pre-SessionActionCount Definition
-- Reverses: 007_property_graph_session_action_count.sql
-- Purpose: Restore the property graph to the state before SessionActionCount was added
-- Note: Must be run before 006_down.sql to allow dropping the column

CREATE OR REPLACE PROPERTY GRAPH AgentMemoryGraph
  NODE TABLES (
    MemoryNode AS Node
      KEY (NodeId)
      PROPERTIES (NodeId, MemoryTier, Label, LogOddsWeight, LastAccessed, VectorData, Attributes, CreatedAt, UpdatedAt)
  )
  EDGE TABLES (
    MemoryEdge AS Edge
      KEY (SourceNodeId, EdgeId)
      SOURCE KEY (SourceNodeId) REFERENCES MemoryNode (NodeId)
      DESTINATION KEY (DestNodeId) REFERENCES MemoryNode (NodeId)
      PROPERTIES (SourceNodeId, EdgeId, DestNodeId, RelType, LogOddsWeight, LastAccessed, Context, CreatedAt, UpdatedAt)
      LABEL (RelType)
  );
