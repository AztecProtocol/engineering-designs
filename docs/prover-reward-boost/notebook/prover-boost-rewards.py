import marimo

__generated_with = "0.13.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import random
    return mo, plt, random


@app.cell
def _():
    precision = int(1e5)
    return (precision,)


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
    The value is bounded to be between `0` and `upper`.

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
        label="Activity Score Upper Limit",
        start=0,
        stop=500,
        show_value=True,
        full_width=True,
        value=50,
    )

    proof_increase = mo.ui.slider(
        label="Increase per proof",
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
def _(plt, proof_increase, proof_probability, random, upper_limit):
    def plot_activity_score(upper_limit=50, p=0.75, proof_increase=2):
        X = [i for i in range(upper_limit * 2)]
        Y = [0]

        for x in X[1:]:
            r = proof_increase if random.random() <= p else 0
            Y.append(min(max(0, Y[-1] + r - 1), upper_limit))

        fig, ax = plt.subplots(figsize=(12, 4))

        ax.plot(X, Y)

        ax.set_title(
            f"Activity Scores as function of time passing (epochs) and probability to produce proof ({upper_limit}, {p:.2%}, {proof_increase})"
        )
        ax.set_ylabel("Activity Score")
        ax.set_xlabel("Epochs")

        return ax


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
    	\max(k - a(x - h)^2, m), & \text{if } x \leq h \\
    	k, & \text{if } x > h
    \end{cases}
    $$

    In here, $k$ acts as the "max" boost that can be hit, and $h$ the score at which this is hit. The value $m$ is the default multiplier.

    Note, that setting $h$ to be equal the `upper` limit that we supplied earlier is a way to have instant decay. As $h$ becomes equal to `upper` note that we cannot hit the $x > h$ case anymore.
    """
    )
    return


@app.cell
def _(mo, precision):
    a = mo.ui.number(label="$a$", start=0, full_width=True, value=5000, step=500)

    k = mo.ui.number(
        label="$k$", start=precision, full_width=True, value=precision * 10
    )

    h = mo.ui.slider(
        label="$h$", start=0, stop=500, show_value=True, full_width=True, value=50
    )

    mo.hstack([a, k, h])
    return a, h, k


@app.cell
def _(a, h, k, plt, precision):
    def prover_weigth(x, a, k, h, m):
        if x > h:
            return int(k)
        else:
            return max(int(k) - int(a) * int(x - h) ** 2, int(m))


    def generate_data(a, k, h, m):
        X = [i for i in range(h + 10)]
        Y = [prover_weigth(x, a, k, h, m) for x in X]

        return X, Y


    def plot_prover_weigth(a, k, h, m):
        X, Y = generate_data(a, k, h, m)

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(X, Y)

        ax.set_title(
            f"Shares as function of activity score (a:{a}, k:{k}, h:{h}, m:{m})"
        )
        ax.set_ylabel("Shares")
        ax.set_xlabel("Activity Score")

        return ax


    plot_prover_weigth(
        a=a.value,
        k=k.value,
        h=h.value,
        m=precision,
    )
    return (generate_data,)


@app.cell
def _(mo):
    mo.md(
        r"""
    # Test Data

    We generate test data that we can use in foundry to ensure that out maths align.
    """
    )
    return


@app.cell
def _(a, generate_data, h, k, precision):
    def generate_json_output(a, k, h, m):
        X, Y = generate_data(a, k, h, m)

        data = {"config": {"a": a, "k": k, "h": h, "m": m}, "xs": X, "ys": Y}

        return data


    generate_json_output(a.value, k.value, h.value, precision)
    return


if __name__ == "__main__":
    app.run()
