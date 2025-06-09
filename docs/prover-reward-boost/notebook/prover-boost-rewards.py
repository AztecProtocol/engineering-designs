import marimo

__generated_with = "0.13.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import random
    import numpy as np

    from pydantic import StrictInt, field_validator, Field
    from pydantic.dataclasses import dataclass
    from dataclasses import fields
    import json
    return StrictInt, dataclass, field_validator, json, mo, np, plt, random


@app.cell
def _():
    precision = int(1e5)
    return (precision,)


@app.cell(hide_code=True)
def _(StrictInt, dataclass, field_validator):
    def bounded_int(min_value: int, max_value: int):
        """
        Decorator for creating bounded integer types with validation
        Inclusive of min_value, exclusive of max_value
        """

        def decorator(cls):
            @dataclass
            class BoundedInt:
                value: StrictInt

                @field_validator("value")
                def check_range(cls, v):
                    if not (min_value <= v < max_value):
                        raise ValueError(
                            f"Value don't satisfy {min_value} <= {v} <= {max_value}"
                        )
                    return v

                def to_dict(self) -> int:
                    # Custom serialization to return just the integer value
                    return self.value

                def __eq__(self, other):
                    if isinstance(other, BoundedInt):
                        return self.value == other.value
                    return False

                def __ne__(self, other):
                    return not self.__eq__(other)

                def __gt__(self, other):
                    return self.value > other.value

                def __ge__(self, other):
                    return self.value >= other.value

                def __lt__(self, other):
                    return self.value < other.value

                def __le__(self, other):
                    return self.value <= other.value

                def __abs__(self):
                    return BoundedInt(value=abs(self.value))

                def __neg__(self):
                    return BoundedInt(value=-self.value)

                def __add__(self, other):
                    if isinstance(other, BoundedInt):
                        result = self.value + other.value
                        if result > max_value:
                            raise OverflowError("Integer overflow")
                        return BoundedInt(value=result)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for +: '{cls.__name__}' and '{type(other)}'"
                        )

                def __sub__(self, other):
                    if isinstance(other, BoundedInt):
                        result = self.value - other.value
                        if result < min_value:
                            raise ValueError("Integer underflow")
                        return BoundedInt(value=result)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for -: '{cls.__name__}' and '{type(other)}'"
                        )

                def __mul__(self, other):
                    if isinstance(other, BoundedInt):
                        result = self.value * other.value
                        if result > max_value:
                            raise OverflowError("Integer overflow")
                        return BoundedInt(value=result)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for *: '{cls.__name__}' and '{type(other)}'"
                        )

                def __truediv__(self, other):
                    if isinstance(other, BoundedInt):
                        if other.value == 0:
                            raise ZeroDivisionError("Division by zero")
                        return BoundedInt(value=self.value // other.value)
                    else:
                        raise TypeError(
                            f"Unsupported operand type for /: '{cls.__name__}' and '{type(other)}'"
                        )

                def mul_div(self, other, denominator, round_up=False):
                    temp = self.value * other.value
                    result = temp // denominator.value
                    if round_up and temp % denominator.value != 0:
                        result += 1
                    return BoundedInt(value=result)

            # Copy the class name and update annotations
            BoundedInt.__name__ = cls.__name__
            BoundedInt.__qualname__ = cls.__qualname__
            return BoundedInt

        return decorator


    @bounded_int(min_value=0, max_value=2**256 - 1)
    class Uint256:
        pass


    @bounded_int(min_value=-(2**255), max_value=2**255 - 1)
    class Int256:
        pass
    return (Uint256,)


@app.cell
def _(mo, precision):
    mo.md(
        rf"""
    # Prover Shares

    Currently a prover have `1` share of the reward.
    To support boosting, we alter this such that a prover will instead have that their number of shares depends on their prior actions. 

    To do so, we will first introduce an "activity score" and then a method to derive the number of shares from that it.

    Every `prover` will have some value `x` that is stored for them specifically reflecting their recent activity. 
    The value is computed fairly simply. 
    Every time an epoch passes, the activity score goes down by 1. 
    Every block the prover produces increases their value with some "proof_increase" value.
    The values are bounded to be between `0` and `upper`, and we apply this "clamp" after the subtraction and again after the addition. 

    $$
    \min(\max(0, curr - 1) + increase, upper)
    $$

    We use `upper` to limit the score in order to constrain how long a boost is maintained after the actor stops proving.

    Beware that this structure means that the score WILL go down, if there is nothing to prove.
    This is acknowledged, since supporting that makes the accounting much simpler and cheaper, as we only need to store a score and a time of that score to be able to derive the current score.

    The score and timestamp is then updated at proof submission.

    For that maths we are generally using precision of {precision}, e.g., the value 1.0 would be represented as {precision}.
    """
    )
    return


@app.cell
def _(mo):
    upper_limit = mo.ui.slider(
        label="Activity Score Upper Limit ($h$)",
        start=0,
        stop=500,
        show_value=True,
        full_width=True,
        value=50,
    )

    proof_increase = mo.ui.slider(
        label="Increase per proof ($pi$)",
        start=1,
        stop=5,
        step=0.125,
        show_value=True,
        full_width=True,
        value=2,
    )


    proof_probability = mo.ui.slider(
        label="Probably of proof production (%)",
        start=0,
        stop=100,
        show_value=True,
        full_width=True,
        value=75,
    )

    mo.hstack([upper_limit, proof_increase, proof_probability])
    return proof_increase, proof_probability, upper_limit


@app.cell
def _(
    Uint256,
    json,
    mo,
    plt,
    precision,
    proof_increase,
    proof_probability,
    random,
    upper_limit,
):
    def plot_activity_score(upper_limit=50, p=0.75, proof_increase=2):
        config = {
            "h": Uint256(int(upper_limit * precision)),
            "pi": Uint256(int(proof_increase * precision)),
        }

        X = [Uint256(i) for i in range(upper_limit * 2)]
        is_proven = [False]
        Y = [Uint256(0)]
        one = Uint256(precision)

        for x in X[1:]:
            a = Y[-1] - one if Y[-1] > one else Uint256(0)
            mark = random.random() <= p
            r = config["pi"] if mark else Uint256(0)

            Y.append(min(a + r, config["h"]))
            is_proven.append(mark)

        fig, ax = plt.subplots(figsize=(12, 4))

        X_r = [x.value for x in X]
        Y_r = [y.value / precision for y in Y]

        ax.plot(X_r, Y_r)

        ax.set_title(
            f"Activity Scores as function of time passing (epochs) and probability to produce proof ({upper_limit}, {p:.2%}, {proof_increase})"
        )
        ax.set_ylabel("Activity Score")
        ax.set_xlabel("Epochs")

        data = json.dumps(
            {
                "config": {k: v.to_dict() for k, v in config.items()},
                "is_proven": is_proven,
                "activity_score": [y.to_dict() for y in Y],
            }
        )

        return mo.vstack([ax, data])


    plot_activity_score(
        upper_limit=upper_limit.value,
        p=proof_probability.value / 100,
        proof_increase=proof_increase.value,
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    By then feeding this activity value as $x$ into the following formula, we compute their share.

    $$
    y(x) = \begin{cases}
    	\max(k - a(h - x)^2, m), & \text{if } x \leq h \\
    	k, & \text{if } x > h
    \end{cases}
    $$

    In here, $k$ acts as the "max" boost that can be hit, and $h$ the score at which this is hit. The value $m$ is the default multiplier.

    Note, that setting $h$ to be equal the `upper` limit that we supplied earlier is a way to have instant decay. As $h$ becomes equal to `upper` note that we cannot hit the $x > h$ case anymore.
    """
    )
    return


@app.cell
def _(mo):
    a = mo.ui.number(label="$a$", start=0, value=0.05, step=0.00125)
    k = mo.ui.number(label="$k$", start=1, value=10)
    mo.hstack([a, k])
    return a, k


@app.cell
def _(Uint256, a, k, mo, np, plt, precision, proof_increase, upper_limit):
    def prover_weigth(x, a, k, h, m):
        if x > h:
            return k
        else:
            lhs = k
            rhs = a * (h - x) * (h - x) / (Uint256(precision**2))
            if lhs < rhs:
                return m
            return max(lhs - rhs, m)


    def plot_prover_weigth(a, k, h, m):
        c = {
            "a": Uint256(int(a * precision)),
            "k": Uint256(int(k * precision)),
            "h": Uint256(int(h * precision)),
            "m": Uint256(int(m * precision)),
        }

        step = proof_increase.value - 1

        X = [Uint256(int(i * precision)) for i in np.arange(0, h + 10, step)]
        Y = [prover_weigth(x, c["a"], c["k"], c["h"], c["m"]) for x in X]

        X_r = [x.value / precision for x in X]
        Y_r = [y.value / precision for y in Y]

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(X_r, Y_r)

        ax.set_title(
            f"Shares as function of activity score (a:{a}, k:{k}, h:{h}, m:{m})"
        )
        ax.set_ylabel("Shares")
        ax.set_xlabel("Activity Score")

        c["pi"] = Uint256(int(proof_increase.value * precision))

        data = {
            "config": {k: v.to_dict() for k, v in c.items()},
            "activity_score": [x.to_dict() for x in X],
            "shares": [y.to_dict() for y in Y],
        }

        return mo.vstack([ax, data])


    plot_prover_weigth(
        a=a.value,
        k=k.value,
        h=upper_limit.value,
        m=1,
    )
    return


if __name__ == "__main__":
    app.run()
