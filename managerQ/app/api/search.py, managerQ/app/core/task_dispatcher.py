from managerQ.app.core.task_dispatcher import task_dispatcher

@router.post("/kg-query", response_model=Dict[str, Any])
async def knowledge_graph_query(
    search_query: SearchQuery,
    user: UserClaims = Depends(get_current_user),
):
    """
    Accepts a natural language query, dispatches it to the knowledge_graph_agent,
    and returns the result from the Gremlin query.
    """
    logger.info(f"Dispatching KG query from '{user.username}': '{search_query.query}'")
    
    try:
        # The task dispatcher will handle sending this to the correct agent
        # and returning the result. This requires the dispatcher to be able
        # to handle synchronous-like request/response patterns.
        # For now, we'll assume a fire-and-forget and the client will need to poll.
        # A better implementation would use WebSockets or a callback mechanism.
        
        task_id = task_dispatcher.dispatch_task(
            prompt=search_query.query,
            agent_personality="knowledge_graph_agent"
        )
        
        # This is a simplified polling mechanism for the demo.
        # A real implementation would be more robust.
        result = await task_dispatcher.await_task_result(task_id, timeout=30)
        
        # The result from the KG agent is expected to be a JSON string
        # representing the graph data.
        return json.loads(result)
        
    except Exception as e:
        logger.error(f"Failed to execute knowledge graph query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute knowledge graph query."
        ) 