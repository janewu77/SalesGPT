import logging
import os
import time
from typing import Any, List, Mapping, Optional

import requests

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
import jwt
logger = logging.getLogger(__name__)

# require packages: 'PyJWT'
# chatGLM https://open.bigmodel.cn
class ZHIPUAI(LLM):
    """ ZhIPUAI ChatGLM LLM service.

    Example:
        .. code-block:: python

            endpoint_url = (
                "https://open.bigmodel.cn/api/paas/v3/model-api/chatglm_lite/invoke"
            )
            ZHIPUAIChatGLM_llm = ZhIPUAI(
                endpoint_url=endpoint_url
            )
    """

    endpoint_url: str = "http://127.0.0.1:8000/"
    """Endpoint URL to use."""
    model_kwargs: Optional[dict] = None
    """Key word arguments to pass to the model."""
    max_token: int = 20000
    """Max token allowed to pass to the model."""
    temperature: float = 0.1
    """LLM model temperature from 0 to 10."""
    # history: List[List] = []
    """History of the conversation"""
    top_p: float = 0.7
    """Top P for nucleus sampling from 0 to 1"""
    # with_history: bool = False
    """Whether to use history or not"""

    @property
    def _llm_type(self) -> str:
        # return "chat_glm"
        return "zhipuai_chat_glm"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"endpoint_url": self.endpoint_url},
            **{"model_kwargs": _model_kwargs},
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call out to a ChatGLM LLM inference endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = ZHIPUAIChatGLM_llm("Who are you?")
        """

        _model_kwargs = self.model_kwargs or {}

        # HTTP headers for authorization
        # headers = {"Content-Type": "application/json"}
        api_key = os.environ.get('ZHIPUAI_API_KEY')
        bear_token = self.generate_token(api_key, 300)
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {bear_token}'
        }

        payload = {
            "prompt": prompt,
            "temperature": self.temperature,
            "max_length": self.max_token,
            "top_p": self.top_p,
        }
        payload.update(_model_kwargs)
        payload.update(kwargs)

        logger.debug(f"ZHIPUAI-ChatGLM payload: {payload}")

        # call api
        try:
            response = requests.post(self.endpoint_url, headers=headers, json=payload)
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error raised by inference endpoint: {e}")

        logger.debug(f"ZHIPUAI-ChatGLM response: {response}")

        if response.status_code != 200:
            raise ValueError(f"Failed with response: {response}")

        try:
            parsed_response = response.json()
            # print(parsed_response)

            # Check if response content does exists
            if isinstance(parsed_response, dict):
                if parsed_response['code'] != 200:
                    raise ValueError(f"Failed with response({parsed_response['code']}): {parsed_response['msg']}")

                # content_keys = "response"
                content_keys = "data"
                if content_keys in parsed_response:
                    text = parsed_response[content_keys]['choices'][0]['content']
                    # data = parsed_response[content_keys][0]
                else:
                    raise ValueError(f"No content in response : {parsed_response}")
            else:
                raise ValueError(f"Unexpected response type: {parsed_response}")

        except requests.exceptions.JSONDecodeError as e:
            raise ValueError(
                f"Error raised during decoding response from inference endpoint: {e}."
                f"\nResponse: {response.text}"
            )

        if stop is not None:
            text = enforce_stop_tokens(text, stop)

        # [1:-1] remove \" in text
        return text[1:-1]

    def generate_token(self, apikey: str, exp_seconds: int):
        try:
            id, secret = apikey.split(".")
        except Exception as e:
            raise Exception("invalid apikey", e)

        payload = {
            "api_key": id,
            "exp": int(round(time.time() * 1000)) + exp_seconds * 1000,
            "timestamp": int(round(time.time() * 1000)),
        }

        return jwt.encode(
            payload,
            secret,
            algorithm="HS256",
            headers={"alg": "HS256", "sign_type": "SIGN"},
        )