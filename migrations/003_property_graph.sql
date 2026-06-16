-- Migration 003: Create Property Graph Definition
-- Purpose: Define property graph for GQL queries on tripartite memory
-- Status: Phase 1B - Schema Foundation

-- Create the property graph that maps tables to graph nodes and edges
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

-- Example GQL queries (for reference, will be used in Phase 2):
-- 
-- -- Retrieve a context window (recent turns)
-- MATCH p = (s:Node {MemoryTier: 'CONTEXT'})-[e]->(m:Node) 
-- WHERE s.NodeId = @session_id 
-- RETURN NODES(p), EDGES(p) 
-- ORDER BY m.CreatedAt DESC LIMIT @window_size;
--
-- -- Retrieve high-weight semantic facts
-- MATCH (n:Node {MemoryTier: 'SEMANTIC'})
-- WHERE n.LogOddsWeight > 2.5
-- RETURN n, n.Attributes;
--
-- -- Multi-hop traversal with weight filtering
-- MATCH p = (seed:Node)-[e1..3]->(related:Node)
-- WHERE seed.MemoryTier = 'SEMANTIC' AND all(edge IN relationships(p) WHERE edge.LogOddsWeight > 0.3)
-- RETURN NODES(p), EDGES(p);
