__all__ = ["generate_args"]

import collections
import typing as T
import random


def _range(l: T.Union[float, int], r: T.Union[float, int]) -> T.Union[float, int]:
    if isinstance(l, float) or isinstance(r, float):
        return random.uniform(l, r)

    return random.randint(l, r)


class Filter(collections.namedtuple("Filter", ["range", "format", "weight"])):
    def apply(self) -> T.Optional[str]:
        if self.range is bool:
            if random.randint(0, 1) == 1:
                return None
            return self.format

        if isinstance(self.range[0], list):
            # multiple ranges
            values = [_range(*ends) for ends in self.range]
            return self.format.format(*values)

        # singular range
        value = _range(*self.range)
        return self.format.format(value)

    def __hash__(self):
        return hash(self.format)

    def __repr__(self):
        return f"<Filter range={self.range!r} format={self.format!r}>"


FILTERS = [
    # volume boost
    Filter([1, 1.5], "volume={}", weight=20),
    # bass boost
    Filter([1.0, 3.0], "bass=g={}", weight=20),
    # high pass filter
    Filter(bool, "highpass", weight=20),
    # low pass filter
    Filter(bool, "lowpass", weight=20),
    # audio "contrast"
    Filter([50, 100], "acontrast={}", weight=10),
    # phaser (modulates waveforms)
    Filter(
        [[0.5, 2], [0.4, 0.8], [1, 2]],
        "aphaser=out_gain={}:decay={}:speed={}",
        weight=5,
    ),
    # speed
    Filter([0.5, 1.0], "atempo={}", weight=10),
    # reverse entire clip
    Filter(bool, "areverse", weight=5),
    # sample rate
    Filter([44100, int(44100 * 1.5)], "asetrate=sample_rate={}", weight=5),
    # "Make audio easier to listen to on headphones."
    Filter(bool, "earwax", weight=5),
    # wacky flanger
    Filter(
        [[0, 30], [0, 10], [0, 100], [0.1, 10.0]],
        "flanger=delay={}:depth={}:width={}:speed={}",
        weight=5,
    ),
    # wacky vibrato
    Filter([[1, 100], [0.5, 1]], "vibrato=f={}:d={}", weight=5),
]


def generate_args() -> T.List[str]:
    bitrate = random.randint(3, 100)

    weights = [filter.weight for filter in FILTERS]
    choices = random.choices(FILTERS, weights, k=random.randint(4, len(FILTERS)))
    filters = list(set(choices))  # deduplicate

    applied = filter(None, [filter.apply() for filter in filters])
    filter_param = ",".join(applied)

    return ["-b:a", f"{bitrate}k", "-af", filter_param]
