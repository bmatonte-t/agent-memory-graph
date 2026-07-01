-- DOWN Migration 003: Drop Property Graph
-- Reverses: 003_property_graph.sql
-- Purpose: Remove the AgentMemoryGraph property graph definition

DROP PROPERTY GRAPH IF EXISTS AgentMemoryGraph;
