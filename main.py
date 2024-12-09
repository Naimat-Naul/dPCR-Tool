import numpy as np
import zipfile
import pandas as pd
import io
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import Label, Button, Entry, messagebox, filedialog, Menu
import seaborn as sns
import os
from datetime import datetime


dragging_vic = False
dragging_fam = False

# Function to load specified CSV files from a .eds file
def load_data_from_eds():
    global current_file, file_label
    zip_file_path = filedialog.askopenfilename(title="Select EDS file", filetypes=[("EDS files", "*.eds")])

    if not zip_file_path:
        messagebox.showwarning("Warning", "No file selected.")
        return None, None, None, None

    current_file = zip_file_path
    file_label.config(text=f"Selected File: {current_file.split('/')[-1]}") 

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        file_names = zip_ref.namelist()

        if len(file_names) < 29:
            messagebox.showerror("Error", "The ZIP file does not contain enough files.")
            return None, None, None, None
        
        Fam = pd.read_csv(io.BytesIO(zip_ref.read(file_names[14])))
        Rox = pd.read_csv(io.BytesIO(zip_ref.read(file_names[15])))
        Vic = pd.read_csv(io.BytesIO(zip_ref.read(file_names[16])))
        Com = pd.read_csv(io.BytesIO(zip_ref.read(file_names[28])))

    return Fam, Rox, Vic, Com


# Function to merge the data
def retrive_data(fam, rox, vic, com):
    data = pd.concat([com, fam.iloc[:, 0], rox.iloc[:, 0], vic.iloc[:, 0]], axis=1)
    data.columns = list(com.columns) + ['famP', 'roxP', 'vicP']
    
    df = data[data['roxP'] == 1].drop(columns=['roxP'])  
    return df


# Function to process data
def process_data(df):
    df['FVP'] = ((df['famP'] == 1) & (df['vicP'] == 1)).astype(int)  
    df['FVN'] = ((df['famP'] == 0) & (df['vicP'] == 0)).astype(int)  
    df.loc[df['FVP'] == 1, ['famP', 'vicP']] = 0  
    return df


# Apply thresholds to FAM and VIC columns
def apply_threshold(data, vic_threshold, fam_threshold):
    data['famP'] = (data['Fam'] >= fam_threshold).astype(int)
    data['vicP'] = (data['Vic'] >= vic_threshold).astype(int)
    return data


# Function to reshape the data for plotting
def reshape_data(df):
    df_long = df.melt(id_vars=['Fam', 'Vic'],  
                      value_vars=['famP', 'vicP', 'FVP', 'FVN'],  
                      var_name='Category', value_name='value')
    df_long = df_long[df_long['value'] == 1]
    return df_long


def con(total_wells, target_wells):
    neg = total_wells - target_wells
    l = np.log(total_wells / neg)
    target_mol = total_wells * l
    partition_vol = total_wells * 0.000755
    copies = target_mol / partition_vol

    return neg, copies


# Function to plot the data with draggable threshold lines
def plot_interactive(df, initial_vic_threshold, initial_fam_threshold):
    global vic_line, fam_line, ax

    df_long = reshape_data(df)
    category_counts = df_long.groupby('Category').size().to_dict()
    labels_with_counts = {
        'famP': f'FAM ({category_counts.get("famP", 0)})',
        'vicP': f'VIC ({category_counts.get("vicP", 0)})',
        'FVP': f'FAM+VIC ({category_counts.get("FVP", 0)})',
        'FVN': f'NO-AMP ({category_counts.get("FVN", 0)})'
    }
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.scatterplot(x='Vic', y='Fam', hue='Category', data=df_long,
                              palette={'vicP': 'red', 'famP': 'blue', 'FVP': 'green', 'FVN': 'yellow'}, ax=ax, size=0.3)

    # Initial threshold lines
    vic_line = ax.axvline(x=initial_vic_threshold, color='red', linestyle='-', label=f'VIC Threshold: {initial_vic_threshold}')
    fam_line = ax.axhline(y=initial_fam_threshold, color='blue', linestyle='-', label=f'FAM Threshold: {initial_fam_threshold}')
    
    ax.set_xlabel("VIC")
    ax.set_ylabel("FAM")
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=[labels_with_counts[label] for label in labels_with_counts], loc='upper right')
    ax.grid(True)
    fig.tight_layout()

    # Event handling for dragging lines
    def on_click(event):
        global dragging_vic, dragging_fam
        if vic_line.contains(event)[0]:
            dragging_vic = True
        elif fam_line.contains(event)[0]:
            dragging_fam = True

    def on_release(event):
        global dragging_vic, dragging_fam
        dragging_vic = False
        dragging_fam = False

    def on_motion(event):
        if dragging_vic:
            vic_line.set_xdata(event.xdata)
            vic_entry.delete(0, 'end')
            vic_entry.insert(0, f'{event.xdata:.2f}')
        elif dragging_fam:
            fam_line.set_ydata(event.ydata)
            fam_entry.delete(0, 'end')
            fam_entry.insert(0, f'{event.ydata:.2f}')

        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('button_press_event', on_click)
    fig.canvas.mpl_connect('button_release_event', on_release)
    fig.canvas.mpl_connect('motion_notify_event', on_motion)


    return fig, ax



# Function to update the plot and concentrations
def update_plot(vic_threshold, fam_threshold):
    global df, vic_line, fam_line, ax

    df = apply_threshold(df.copy(), vic_threshold, fam_threshold)
    df = process_data(df)
    
    
    # Clear the plot and redraw with updated thresholds
    ax.clear()
    df_long = reshape_data(df)
    category_counts = df_long.groupby('Category').size().to_dict()
    sns.scatterplot(x='Vic', y='Fam', hue='Category', data=df_long,
                    palette={'vicP': 'red', 'famP': 'blue', 'FVP': 'green', 'FVN': 'yellow'}, ax=ax, size=0.3)
    
    vic_line = ax.axvline(x=vic_threshold, color='red', linestyle='-', label=f'VIC Threshold: {vic_threshold}')
    fam_line = ax.axhline(y=fam_threshold, color='blue', linestyle='-', label=f'FAM Threshold: {fam_threshold}')

    ax.set_xlabel("VIC")
    ax.set_ylabel("FAM")
    ax.grid(True)
    

    labels_with_counts = {
        'famP': f'FAM ({category_counts.get("famP", 0)})',
        'vicP': f'VIC ({category_counts.get("vicP", 0)})',
        'FVP': f'FAM+VIC ({category_counts.get("FVP", 0)})',
        'FVN': f'NO-AMP ({category_counts.get("FVN", 0)})'
    }
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=[labels_with_counts[label] for label in labels_with_counts], loc='upper right')


    # Redraw the canvas to reflect changes
    ax.figure.canvas.draw_idle()




def load_data():
    global fam, rox, vic, com, df, root
    fam, rox, vic, com = load_data_from_eds()
    if fam is not None:
        df = retrive_data(fam, rox, vic, com)
        df = process_data(df)

        
def plot():
    global canvas, ax     
    initial_vic_threshold = df[df['vicP'] == 1]['Vic'].min()  
    initial_fam_threshold = df[df['famP'] == 1]['Fam'].min()  
        
    # Set initial threshold values in the entry boxes
    vic_entry.delete(0, 'end')
    vic_entry.insert(0, str(initial_vic_threshold))
        
    fam_entry.delete(0, 'end')
    fam_entry.insert(0, str(initial_fam_threshold))

    # If a plot is already present, remove it
    if 'canvas' in globals() and canvas is not None:
        canvas.get_tk_widget().destroy()
        canvas = None
        
    fig, ax = plot_interactive(df, initial_vic_threshold, initial_fam_threshold)
        
    # Embed the Matplotlib plot in Tkinter
    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    canvas.get_tk_widget().place(x=0, y=0, width=600, height=400)
    canvas.draw()


    toolbar = NavigationToolbar2Tk(canvas, graph_frame)
    toolbar.update()
    toolbar.place(x=1, y=410, width=600)

    # Configure grid weights to ensure proper resizing
    graph_frame.grid_columnconfigure(0, weight=1)
    graph_frame.grid_rowconfigure(0, weight=1)
    graph_frame.grid_rowconfigure(1, weight=0)



def calculate():
    global df, negfam, copiesFAM, negvic, copiesVIC
    if df is None or current_file is None:
        messagebox.showerror("Error", "No data loaded.")
        return

    total_wells = len(df)
    fam_wells = len(df[df['famP'] == 1]) + len(df[df['FVP'] == 1])
    vic_wells = len(df[df['vicP'] == 1]) + len(df[df['FVP'] == 1])
    negfam, copiesFAM = con(total_wells, fam_wells)
    negvic, copiesVIC = con(total_wells, vic_wells)
    concentration_label.config(text=f"Copies/microliter (FAM): {copiesFAM:.4f} \t Copies/microliter (VIC): {copiesVIC:.4f}")
   

def save_concentrations():
    # Extract file details
    file_name = os.path.basename(current_file)
    date_str = file_name.split('_')[0]
    file_date = datetime.strptime(date_str, '%y%m%d').strftime('%d %B %Y')

    save_path = filedialog.askopenfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        title="Select File to Update"
    )

    if not save_path:
        messagebox.showinfo("Cancelled", "Operation cancelled.")
        return

    new_data = pd.DataFrame({
        'File': [file_name],
        'Date': [file_date],
        '# of Neg (FAM)': [negfam],
        'Copies/microliter (FAM)': [copiesFAM],
        '# of Neg (VIC)': [negvic],
        'Copies/microliter (VIC)': [copiesVIC]
    })

    try:
        if os.path.exists(save_path):
            existing_data = pd.read_csv(save_path)

            if file_name in existing_data['File'].values:
                for col in new_data.columns:
                    existing_data.loc[existing_data['File'] == file_name, col] = new_data[col].values[0]
            else:
                existing_data = pd.concat([existing_data, new_data], ignore_index=True)

            existing_data.to_csv(save_path, index=False)
        else:
            messagebox.showerror("Error", "The selected file does not exist.")

        # Confirmation message
        messagebox.showinfo("Success", f"Concentrations updated in {save_path}.")
    except PermissionError:
        messagebox.showerror(
            "File Locked",
            "The selected file is currently open in another application. "
            "Please close the file and try again."
        )
    except Exception as e:
        messagebox.showerror(
            "Error",
            f"An unexpected error occurred:\n{str(e)}"
        )

def close_file():
    global fam, rox, vic, com, df, root, ax
    fam, rox, vic, com, df = None, None, None, None, None
    try:
        if ax:
            ax.clear()
            ax.figure.canvas.draw_idle()
    except NameError:
        pass

    vic_entry.delete(0, 'end')
    fam_entry.delete(0, 'end')

    messagebox.showinfo("Close File", "The file has been closed, and the plot has been cleared.")



 # Main application window
def main_app():
    global vic_entry, fam_entry, concentration_label, fam, rox, vic, com, df, root, file_label, graph_frame

    root = tk.Tk()
    root.title("dPCR Analyser")
    root.geometry("1280x720")  

    # Menu bar
    menu = Menu(root)
    root.config(menu=menu)

    file_menu = Menu(menu, tearoff=0)
    file_menu.add_command(label="Open", command=load_data)
    file_menu.add_command(label="Close", command=close_file)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)
    menu.add_cascade(label="File", menu=file_menu)

    
     # Configure the grid layout to allow resizing
    root.grid_rowconfigure(0, weight=0)  # Row for the menu
    root.grid_rowconfigure(1, weight=1)  # Row for the content (scrollable area)
    root.grid_columnconfigure(0, weight=1)  # Column for the canvas area
    root.grid_columnconfigure(1, weight=0)

    # Create a canvas widget for scrollable window
    canvas = tk.Canvas(root)
    canvas.grid(row=1, column=0, sticky="nsew")

    v_scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    v_scrollbar.grid(row=1, column=1, sticky="ns")

    h_scrollbar = tk.Scrollbar(root, orient="horizontal", command=canvas.xview)
    h_scrollbar.grid(row=2, column=0, sticky="ew")

    canvas.config(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    # Create a frame inside the canvas to hold all widgets
    main_frame = tk.Frame(canvas)
    canvas.create_window((0, 0), window=main_frame, anchor="nw")

    
    main_frame.bind(
        "<Configure>",
        lambda e: canvas.config(scrollregion=canvas.bbox("all"))
    )


    # File label
    file_label = Label(main_frame, text="No file selected")
    file_label.grid(row=0, column=1, pady=10, sticky="n")

    # Plot/Visualize button
    plot_button = Button(main_frame, text="Visualize", command=plot)
    plot_button.grid(row=1, column=1, pady=10)

    # Graph placeholder
    global graph_frame
    graph_frame = tk.Frame(main_frame, width=600, height=450)
    graph_frame.grid(row=2, column=0, padx=20, pady=10)
    graph_frame.grid_propagate(False)  

    # FAM and VIC thresholds
    thresholds_frame = tk.Frame(main_frame)
    thresholds_frame.grid(row=2, column=2, padx=20, pady=10, sticky="ne")

    Label(thresholds_frame, text="VIC Threshold:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    vic_entry = Entry(thresholds_frame, width=15)
    vic_entry.grid(row=0, column=1, padx=5, pady=5)

    Label(thresholds_frame, text="FAM Threshold:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    fam_entry = Entry(thresholds_frame, width=15)
    fam_entry.grid(row=1, column=1, padx=5, pady=5)

    # Apply Thresholds button
    apply_button = Button(thresholds_frame, text="Apply Thresholds", command=lambda: update_plot(float(vic_entry.get()), float(fam_entry.get())))
    apply_button.grid(row=2, column=0, columnspan=2, pady=10)

    # Calculate Concentrations button
    calculate_button = Button(main_frame, text="Calculate Copies", command=calculate)
    calculate_button.grid(row=3, column=0, pady=10)

    # Concentration label
    concentration_label = Label(main_frame, text="")
    concentration_label.grid(row=4, column=0, pady=10)

    # Save button
    save_button = Button(main_frame, text="Save", command=save_concentrations)
    save_button.grid(row=5, column=0, pady=10)

    def on_close():
   
        root.quit()  
        root.destroy() 

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main_app()
