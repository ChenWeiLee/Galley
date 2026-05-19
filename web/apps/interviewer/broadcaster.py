"""
ChannelsBroadcaster — implements `domain.ports.LiveBroadcaster`.

Used by Step 8's RecordVerdictUseCase to push verdict events to interviewer
observers without importing Channels into the domain layer.
"""
from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from domain.ports.live_broadcaster import LiveBroadcaster


class ChannelsBroadcaster(LiveBroadcaster):
    def push(self, session_id: str, event_type: str, payload: dict) -> None:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"session_{session_id}",
            {"type": f"{event_type}.broadcast", **payload},
        )
