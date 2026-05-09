from rest_framework.renderers import JSONRenderer


class StandardResponseRenderer(JSONRenderer):
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = {
            "success": True,
            "data": data,
            "errors": None
        }

        return super().render(
            response,
            accepted_media_type,
            renderer_context
        )