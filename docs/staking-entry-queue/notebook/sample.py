import marimo

__generated_with = "0.13.15"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import math
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.stats import hypergeom
    return hypergeom, math, mo, plt


@app.cell(hide_code=True)
def _(mo):
    existing_validators = mo.ui.slider(
        100, 8192, value=4096, label="Total Existing Validators"
    )
    new_validators_added = mo.ui.slider(
        1, 256, value=204, label="New Validators Added to Pool"
    )
    committee_size = mo.ui.slider(
        32, 64, value=48, label="Committee Size"
    )
    return committee_size, existing_validators, new_validators_added


@app.cell
def _(committee_size, existing_validators, mo, new_validators_added):
    mo.md(
        f"""
    {existing_validators}\n
    {new_validators_added}\n
    {committee_size}
    """
    )
    return


@app.cell(hide_code=True)
def _(
    committee_size,
    existing_validators,
    hypergeom,
    new_validators_added,
    plt,
):

    minimum_probability_graphed = 0.0001

    k_values = []
    probabilities = []
    max_possible_k = min(committee_size.value, new_validators_added.value)
    total_validators = existing_validators.value + new_validators_added.value

    # Loop k from 1 upwards, and stop when the probability gets too low
    for k in range(1, max_possible_k + 1):
        # Calculate P(X >= k), which is 1 - P(X <= k-1)
        prob = 1 - hypergeom.cdf(
            k - 1,                           # The upper bound of the CDF
            total_validators,                # M: Total validator pool size
            new_validators_added.value,      # n: Total new validators in the pool
            committee_size.value             # N: The committee size
        )

        if prob < minimum_probability_graphed:
            break 
        k_values.append(k)
        probabilities.append(prob)


    # --- Plotting ---
    fig, ax = plt.subplots(figsize=(10, 6))

    if k_values:
        bars = ax.bar(k_values, probabilities, color='mediumpurple', ec='black', width=0.6)

        # Add text labels on top of bars
        for bar in bars:
            yval = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2.0, yval,
                f'{yval:.3%}', ha='center', va='bottom', fontsize=10
            )

        ax.set_xticks(k_values)

    # Add clear labels and title reflecting the new logic
    ax.set_xlabel("Number of New Validators in the Committee (k)", fontsize=12)
    ax.set_ylabel("Probability of AT LEAST k (P(X >= k))", fontsize=12)
    title_text = (
        f"Cumulative Probability of Drawing At Least k New Validators\n"
        f"Pool: {existing_validators.value} Existing + {new_validators_added.value} New | "
        f"Committee Size: {committee_size.value}"
    )
    ax.set_title(title_text, fontsize=14, pad=15)

    # Format y-axis as a percentage
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.3%}'))

    # Set a clean y-axis limit
    ax.set_ylim(0, 1.0) # Cumulative probability can go up to 100%

    plt.tight_layout()
    # Display the plot in Marimo
    fig
    return (total_validators,)


@app.cell(hide_code=True)
def _(
    committee_size,
    existing_validators,
    hypergeom,
    math,
    mo,
    new_validators_added,
    total_validators,
):
    k_threshold = math.ceil(committee_size.value / 3)

    # 3. Calculate the probability P(X >= k_threshold)
    if k_threshold > new_validators_added.value:
        prob_one_third = 0.0
    else:
        # Otherwise, calculate P(X >= k) = 1 - P(X <= k-1)
        prob_one_third = 1 - hypergeom.cdf(
            k_threshold - 1,        # k - 1
            total_validators,       # M: Total pool
            new_validators_added.value,     # n: Successes in pool
            committee_size.value           # N: Sample size
        )

    epoch_duration_s = 32*36
    num_drains_for_double = math.ceil(committee_size.value / new_validators_added.value)
    seconds_per_day = 60*60*24

    result_text = f"""
    A committee of **{committee_size.value}** members requires **{k_threshold}** seats for ⅓ control.

    Given that **{new_validators_added.value}** new validators are added each epoch, and the existing validator set has **{existing_validators.value}**, the probability of new validators gaining at least ⅓ of the seats is **{prob_one_third:.12%}**.

    Considering an epoch duration of **{epoch_duration_s}** seconds, it will take **{num_drains_for_double * epoch_duration_s / 60 / 60} hours** for the validator set to double in size, and a maximum of **{math.floor(new_validators_added.value * seconds_per_day / epoch_duration_s)}** validators can be added per day.
    """

    mo.md(result_text)
    return


@app.cell
def _():


    return


if __name__ == "__main__":
    app.run()
