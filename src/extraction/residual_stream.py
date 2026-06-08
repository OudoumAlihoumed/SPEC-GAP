import torch
from transformer_lens import HookedTransformer
from jaxtyping import Float
from torch import Tensor

COMMITTED_LAYERS = (16, 20, 24)
EXPLORATORY_LAYERS = tuple(range(13, 25))
DEFAULT_LAYERS = COMMITTED_LAYERS
MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
HIDDEN_DIM = 4096


def load_model(
    model_name: str = MODEL_NAME,
    device: str = "cuda",
    dtype: torch.dtype = torch.float16,
) -> HookedTransformer:
    model = HookedTransformer.from_pretrained(
        model_name,
        device=device,
        dtype=dtype,
    )
    model.eval()
    return model


def _get_cache_filter(layers: tuple[int, ...]):
    layer_set = set(layers)

    def name_filter(name: str) -> bool:
        if not name.endswith("hook_resid_post"):
            return False
        parts = name.split(".")
        layer_idx = int(parts[1])
        return layer_idx in layer_set

    return name_filter


def extract_residual_stream(
    model: HookedTransformer,
    prompts: list[str],
    layers: tuple[int, ...] = DEFAULT_LAYERS,
    token_position: str | int = "last",
    batch_size: int = 1,
    prepend_bos: bool = True,
) -> dict[int, Float[Tensor, "n_prompts hidden"]]:
    results = {layer: [] for layer in layers}
    name_filter = _get_cache_filter(layers)

    for i in range(0, len(prompts), batch_size):
        batch = prompts[i : i + batch_size]
        tokens = model.to_tokens(batch, prepend_bos=prepend_bos)

        with torch.no_grad():
            _, cache = model.run_with_cache(
                tokens,
                names_filter=name_filter,
            )

        for layer in layers:
            hook_name = f"blocks.{layer}.hook_resid_post"
            activations = cache[hook_name]

            if token_position == "last":
                act = activations[:, -1, :]
            elif token_position == "all":
                act = activations
            elif isinstance(token_position, int):
                act = activations[:, token_position, :]
            else:
                raise ValueError(f"Unknown token_position: {token_position}")

            results[layer].append(act.cpu())

        del cache
        torch.cuda.empty_cache()

    for layer in layers:
        results[layer] = torch.cat(results[layer], dim=0)

    return results
