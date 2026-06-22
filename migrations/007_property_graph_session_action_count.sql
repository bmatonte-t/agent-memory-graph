-- Migration 007: Expose session action count in the property graph
-- Purpose: Keep the property graph mapping aligned with the MemoryNode schema.

CREATE OR REPLACE PROPERTY GRAPH AgentMemoryGraph
  NODE TABLES (
    MemoryNode AS Node
      KEY (NodeId)
      PROPERTIES (NodeId, MemoryTier, Label, LogOddsWeight, LastAccessed, VectorData, Attributes, SessionActionCount, CreatedAt, UpdatedAt)
  )
  EDGE TABLES (
    MemoryEdge AS Edge
      KEY (SourceNodeId, EdgeId)
      SOURCE KEY (SourceNodeId) REFERENCES MemoryNode (NodeId)
      DESTINATION KEY (DestNodeId) REFERENCES MemoryNode (NodeId)
      PROPERTIES (SourceNodeId, EdgeId, DestNodeId, RelType, LogOddsWeight, LastAccessed, Context, CreatedAt, UpdatedAt)
      LABEL (RelType)
  );
