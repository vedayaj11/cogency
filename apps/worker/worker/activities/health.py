from temporalio import activity


@activity.defn
async def ping(message: str = "pong") -> str:
    activity.logger.info("ping", extra={"message": message})
    return message
